#!/usr/bin/env python3
"""
Material Acquisition Plan — given a blueprint and mining setup, computes:
  1. Raw ore needed per refinery method/yield scenario
  2. Mining trip estimates (worst / middle / best) from rock concentration data
  3. Refineries ranked by user preference (nearest / yield / economy / speed)
  4. Per-material refining economics (refine vs sell raw, selective decision)
  5. Full expedition economics summary

Usage:
    python3 scripts/query/material_acquisition_plan.py \\
        --blueprint "Yeager" \\
        --ship prospector \\
        --location "Lagrange A" \\
        --system Stanton \\
        --refinery-pref yield \\
        --refine-what selective

Options:
    --refinery-pref   nearest | yield | economy | speed  (default: yield)
    --refine-what     all | needed | selective           (default: selective)
    --method          override method name (e.g. "Dinyx Solventation")

Notes:
  - Base refinery yield %: game-verified approximations (±2-5%).
  - Refinery fees: game approximations (~6-14% of refined value by cost rating).
  - Trip estimates derived from rock composition concentration ranges in game data.
  - Prices fetched live from UEX API (no auth required).
"""

import argparse
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

# ── Constants (game-verified approximations) ──────────────────────────────────

# Base yield % by method quality rating (1=low, 2=medium, 3=high)
BASE_YIELD_PCT = {3: 79, 2: 72, 1: 64}

# Refinery fee % of refined value by method cost rating (1=low, 2=medium, 3=high)
REFINERY_FEE_PCT = {1: 6, 2: 10, 3: 14}

# Travel time overhead constants (spool + calibration, seconds)
QD_OVERHEAD_S = 30

# Quantum speed override for ships where wiki data may be stock (before QD swap)
# Only used if wiki ships.json is unavailable
FALLBACK_QD_SPEED_GMS = {
    "prospector": 0.215,
    "golem":      0.215,
    "mole":       0.220,
}


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> list | dict:
    if not path.exists():
        sys.exit(f"ERROR: {path} not found. Run scripts/update_cache.sh first.")
    with open(path) as f:
        return json.load(f)


def load_blueprints() -> dict:
    version = (REPO_ROOT / "data" / "VERSION").read_text().strip()
    return load_json(REPO_ROOT / "data" / "raw" / version / "crafting_blueprints.json")


def load_mining_data() -> dict:
    version = (REPO_ROOT / "data" / "VERSION").read_text().strip()
    return load_json(REPO_ROOT / "data" / "raw" / version / "mining_data.json")


def load_uex(filename: str) -> list | dict:
    return load_json(REPO_ROOT / "data" / "uex" / filename)


def load_wiki_ships() -> dict:
    path = REPO_ROOT / "data" / "wiki" / "ships.json"
    return json.load(open(path)) if path.exists() else {}


# ── Blueprint helpers ─────────────────────────────────────────────────────────

def get_blueprint_slots(bp_name: str, bp_data: dict) -> list[dict]:
    bps = bp_data["blueprints"]
    match = next(
        (b for b in bps if (b.get("productName") or "").lower() == bp_name.lower()),
        None,
    ) or next(
        (b for b in bps if bp_name.lower() in (b.get("productName") or "").lower()),
        None,
    )
    if not match:
        return []
    tier = match["tiers"][0] if match.get("tiers") else {}
    slots = []
    for slot in tier.get("slots", []):
        opt = slot["options"][0] if slot.get("options") else {}
        material = opt.get("resourceName") or opt.get("itemName")
        qty = opt.get("quantity")
        if material and qty:
            slots.append({
                "slot_name": slot["name"],
                "material": material,
                "refined_scu": qty,
                "material_type": opt.get("type", "resource"),
            })
    return slots


# ── Concentration helpers ─────────────────────────────────────────────────────

def get_concentration(material_name: str, mining_data: dict) -> dict | None:
    """
    Return concentration data for a material from the compositions.
    Two scenario types:
      'quality'  — qualityScale=1.0, lower concentration → targets high-quality ore
      'quantity' — qualityScale<1.0,  higher concentration → bulk ore, lower quality
    """
    elements = mining_data["mineableElements"]
    compositions = mining_data["compositions"]

    # Find element GUID
    el_guid = next(
        (guid for guid, el in elements.items()
         if material_name.lower() in (el.get("materialName") or "").lower()
         or material_name.lower() in (el.get("name") or "").lower()),
        None,
    )
    if not el_guid:
        return None

    quality_parts = []   # qualityScale = 1.0 (premium ore)
    quantity_parts = []  # qualityScale < 1.0 (bulk ore)

    for comp in compositions.values():
        for part in comp.get("parts", []):
            if part.get("elementGuid") != el_guid:
                continue
            qs = part.get("qualityScale", 1.0)
            entry = {
                "min_pct": part["minPercent"],
                "max_pct": part["maxPercent"],
                "avg_pct": (part["minPercent"] + part["maxPercent"]) / 2,
                "quality_scale": qs,
            }
            if qs >= 1.0:
                quality_parts.append(entry)
            else:
                quantity_parts.append(entry)

    if not quality_parts and not quantity_parts:
        return None

    def agg(parts):
        if not parts:
            return None
        return {
            "min_pct": min(p["min_pct"] for p in parts),
            "max_pct": max(p["max_pct"] for p in parts),
            "avg_pct": sum(p["avg_pct"] for p in parts) / len(parts),
        }

    return {
        "quality_rocks": agg(quality_parts),   # high-quality, lower concentration
        "quantity_rocks": agg(quantity_parts),  # bulk ore, higher concentration
    }


# ── Refinery helpers ──────────────────────────────────────────────────────────

def get_terminal_yield_bonuses(terminal_name: str, materials: list[str],
                                yields_data: list) -> dict[str, int]:
    """Return {material_raw_name: yield_bonus_pct} for a given refinery terminal."""
    bonuses = {}
    for row in yields_data:
        if terminal_name.lower() not in (row.get("terminal_name") or "").lower():
            continue
        comm = row.get("commodity_name", "")
        for mat in materials:
            if mat.lower() in comm.lower():
                # Use weekly average if available, else current
                val = row.get("value_week") or row.get("value") or 0
                bonuses[mat] = val
    return bonuses


def get_ship_quantum_speed_gms(ship_name: str, wiki_ships: dict) -> float:
    """Return quantum speed in Gm/s for a ship."""
    ship = wiki_ships.get(ship_name.lower(), {})
    speed_mms = ship.get("quantum", {}).get("speed_mms")
    if speed_mms:
        return speed_mms / 1000  # Mm/s → Gm/s
    return FALLBACK_QD_SPEED_GMS.get(ship_name.lower(), 0.215)


def fetch_terminal_distance(origin_id: int, dest_id: int) -> float | None:
    """Fetch distance in Gm between two terminals from UEX API."""
    url = f"https://api.uexcorp.uk/2.0/terminals_distances"
    params = urllib.parse.urlencode({
        "id_terminal_origin": origin_id,
        "id_terminal_destination": dest_id,
    })
    headers = {"User-Agent": "starcitizen-scmdb/1.0", "Accept": "application/json"}
    token = os.environ.get("UEX_API_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(f"{url}?{params}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        dist = data.get("data", {}).get("distance")
        return float(dist) if dist else None
    except Exception:
        return None


def fetch_live_prices(materials: list[str], system: str | None) -> dict:
    """Fetch sell prices for both raw and refined forms of each material."""
    commodities = load_uex("commodities.json")
    comm_index = {c["name"]: c for c in commodities}

    def raw_name(mat):
        for n, c in comm_index.items():
            if mat.lower() in n.lower() and c.get("is_raw", 0) == 1:
                return n
        return None

    def refined_name(mat):
        candidates = [n for n, c in comm_index.items()
                      if mat.lower() in n.lower().replace(" ore","").replace(" (raw)","").replace(" (ore)","")
                      and c.get("is_raw", 0) == 0]
        return min(candidates, key=len) if candidates else None

    url_base = "https://api.uexcorp.uk/2.0/commodities_prices"
    headers = {"User-Agent": "starcitizen-scmdb/1.0", "Accept": "application/json"}

    results = {}
    for mat in materials:
        entry = {}
        for form, name_fn in [("raw", raw_name), ("refined", refined_name)]:
            name = name_fn(mat)
            if not name:
                continue
            params = {"commodity_name": name}
            try:
                req = urllib.request.Request(
                    f"{url_base}?{urllib.parse.urlencode(params)}", headers=headers
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read())
                rows = data.get("data", [])
                if system:
                    rows = [r for r in rows if r.get("star_system_name") == system]
                sellable = sorted(
                    [r for r in rows if (r.get("price_sell") or 0) > 0],
                    key=lambda r: -(r.get("price_sell") or 0),
                )
                if sellable:
                    entry[form] = {
                        "commodity_name": name,
                        "best_price_sell": sellable[0]["price_sell"],
                        "best_terminal": sellable[0].get("terminal_name"),
                        "best_location": (
                            sellable[0].get("space_station_name")
                            or sellable[0].get("outpost_name")
                            or sellable[0].get("planet_name")
                        ),
                    }
            except Exception:
                pass
            time.sleep(0.3)
        results[mat] = entry
    return results


# ── Trip estimate ─────────────────────────────────────────────────────────────

def trip_estimate(total_raw_scu: float, ship_cargo: float) -> int:
    return max(1, math.ceil(total_raw_scu / ship_cargo))


# ── Ranking helpers ───────────────────────────────────────────────────────────

def score_refinery(terminal: dict, bonuses: dict, methods: list,
                   pref: str, travel_min: float | None,
                   materials: list[str]) -> float:
    """Return a score for ranking refineries. Higher = better."""
    if pref == "nearest":
        if travel_min is None:
            return -999
        return -travel_min  # lower travel = higher score

    if pref == "yield":
        # Sum of yield bonuses across target materials
        return sum(bonuses.get(m, 0) for m in materials)

    if pref == "economy":
        # yield bonus minus implied cost (higher cost rating = penalty)
        best_method_cost = min(m.get("rating_cost", 2) for m in methods)
        yield_score = sum(bonuses.get(m, 0) for m in materials)
        return yield_score - (best_method_cost * 5)

    if pref == "speed":
        # Prefer fast methods; yield bonus as tiebreaker
        best_method_speed = max(m.get("rating_speed", 2) for m in methods)
        return best_method_speed * 10 + sum(bonuses.get(m, 0) for m in materials)

    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blueprint", required=True)
    parser.add_argument("--ship", default="prospector")
    parser.add_argument("--location", default=None, help="Mining location name")
    parser.add_argument("--system", default="Stanton")
    parser.add_argument("--refinery-pref", default="yield",
                        choices=["nearest", "yield", "economy", "speed"])
    parser.add_argument("--refine-what", default="selective",
                        choices=["all", "needed", "selective"])
    parser.add_argument("--method", default=None, help="Override refinery method name")
    parser.add_argument("--top-refineries", type=int, default=5)
    args = parser.parse_args()

    # ── Load data ──
    bp_data = load_blueprints()
    mining_data = load_mining_data()
    methods_raw = load_uex("refinery_methods.json")
    yields_data = load_uex("refinery_yields.json")
    ref_terminals = load_uex("refinery_terminal_ids.json")
    wiki_ships = load_wiki_ships()

    # Ship cargo and quantum speed
    ship_key = args.ship.lower()
    SHIP_CARGO = {"prospector": 12, "golem": 12, "mole": 96}
    ship_cargo = SHIP_CARGO.get(ship_key, 12)
    qd_speed_gms = get_ship_quantum_speed_gms(ship_key, wiki_ships)

    # Method lookup
    methods_by_name = {m["name"]: m for m in methods_raw}
    if args.method and args.method not in methods_by_name:
        print(f"WARNING: method '{args.method}' not found. Available: {list(methods_by_name)}", file=sys.stderr)

    # ── Blueprint slots ──
    slots = get_blueprint_slots(args.blueprint, bp_data)
    if not slots:
        print(json.dumps({"error": f"Blueprint '{args.blueprint}' not found."}))
        return

    material_names = [s["material"] for s in slots]

    # ── Concentration data ──
    concentration = {
        s["material"]: get_concentration(s["material"], mining_data)
        for s in slots
    }

    # ── Live prices ──
    print("Fetching live prices...", file=sys.stderr)
    prices = fetch_live_prices(material_names, args.system)

    # ── Per-material plan ──
    material_plans = []
    for slot in slots:
        mat = slot["material"]
        needed_refined = slot["refined_scu"]
        conc = concentration.get(mat)
        price_data = prices.get(mat, {})

        # Yield scenarios: apply each method rating to compute raw ore needed
        scenarios = {}
        for rating, base_yield in BASE_YIELD_PCT.items():
            label = {3: "high_yield", 2: "medium_yield", 1: "low_yield"}[rating]
            example_methods = [m["name"] for m in methods_raw if m.get("rating_yield") == rating]
            # Raw ore needed (before terminal yield bonus — computed per refinery)
            raw_needed = round(needed_refined / (base_yield / 100), 3)
            scenarios[label] = {
                "base_yield_pct": base_yield,
                "raw_ore_needed_scu": raw_needed,
                "example_methods": example_methods,
                "note": f"With {base_yield}% base yield, need {raw_needed} SCU raw ore for {needed_refined} SCU refined",
            }

        # Trip estimate per scenario (concentration × cargo)
        trip_scenarios = []
        if conc:
            # High-quality rocks (lower concentration) — targeting best material
            if conc.get("quality_rocks"):
                qr = conc["quality_rocks"]
                for sc_label, sc_raw in [
                    ("worst",  scenarios["low_yield"]["raw_ore_needed_scu"]),
                    ("middle", scenarios["medium_yield"]["raw_ore_needed_scu"]),
                    ("best",   scenarios["high_yield"]["raw_ore_needed_scu"]),
                ]:
                    # Conservative fill: only part of the hold is target material
                    fill_pct = {"worst": qr["min_pct"], "middle": qr["avg_pct"], "best": qr["max_pct"]}[sc_label]
                    ore_per_trip = ship_cargo * (fill_pct / 100)
                    trips = trip_estimate(sc_raw, ore_per_trip)
                    trip_scenarios.append({
                        "scenario": sc_label,
                        "rock_type": "quality (high material grade)",
                        "concentration_pct": round(fill_pct, 1),
                        "ore_per_full_run_scu": round(ore_per_trip, 2),
                        "raw_needed_scu": sc_raw,
                        "trips": trips,
                    })
            # High-concentration rocks — bulk runs, lower quality
            if conc.get("quantity_rocks"):
                qr = conc["quantity_rocks"]
                ore_per_trip = ship_cargo * (qr["avg_pct"] / 100)
                trips = trip_estimate(scenarios["high_yield"]["raw_ore_needed_scu"], ore_per_trip)
                trip_scenarios.append({
                    "scenario": "bulk",
                    "rock_type": "quantity (high concentration, lower grade)",
                    "concentration_pct": round(qr["avg_pct"], 1),
                    "ore_per_full_run_scu": round(ore_per_trip, 2),
                    "raw_needed_scu": scenarios["high_yield"]["raw_ore_needed_scu"],
                    "trips": trips,
                })

        # Economics
        raw_price = (price_data.get("raw") or {}).get("best_price_sell", 0)
        refined_price = (price_data.get("refined") or {}).get("best_price_sell", 0)
        economics = None
        if refined_price:
            # Middle yield scenario for economics
            base = BASE_YIELD_PCT[2] / 100
            fee_pct = REFINERY_FEE_PCT[2] / 100
            refined_value_per_raw_scu = refined_price * base * (1 - fee_pct)
            worth_refining = refined_value_per_raw_scu > (raw_price or 0)
            economics = {
                "raw_sell_price_per_scu": raw_price or "not_found",
                "refined_sell_price_per_scu": refined_price,
                "best_sell_terminal": (price_data.get("refined") or {}).get("best_terminal"),
                "est_refined_value_per_raw_scu": round(refined_value_per_raw_scu, 0),
                "worth_refining": worth_refining,
                "reason": (
                    f"Refined value after medium-yield + fee ≈ {refined_value_per_raw_scu:,.0f} aUEC/SCU raw"
                    f" {'>' if worth_refining else '<'} raw sell {raw_price or 'N/A'} aUEC/SCU"
                ),
                "note": "Fee % and yield % are approximations. Verify in-game refinery interface.",
            }

        material_plans.append({
            "material": mat,
            "slot_name": slot["slot_name"],
            "refined_needed_scu": needed_refined,
            "concentration": conc,
            "yield_scenarios": scenarios,
            "trip_scenarios": trip_scenarios,
            "prices": price_data,
            "economics": economics,
        })

    # ── Refinery ranking ──
    stanton_refs = [t for t in ref_terminals if t.get("star_system_name") == args.system]

    # Map location name to a nearby reference terminal for distance calc
    # Heuristic: Lagrange A → ARC-L1 (id=246); default to ARC-L1
    LOCATION_TO_REF_TERMINAL = {
        "lagrange a": 246, "arc-l1": 246,
        "lagrange b": 246, "arc-l2": 247,
        "lagrange e": 246, "arc-l5": 246,
        "lagrange f": 248, "hur-l1": 248,
        "yela":       245, "cru-l1": 245,
        "aberdeen":   248, "arial": 248, "hurston": 248,
        "lyria":      245, "wala": 245,
        "microtech":  244, "mic-l5": 244,
    }
    loc_key = (args.location or "").lower()
    origin_id = next(
        (v for k, v in LOCATION_TO_REF_TERMINAL.items() if k in loc_key), 246
    )

    ranked_refineries = []
    for term in stanton_refs:
        term_id = term["id"]
        term_name = term["name"] or ""

        # Yield bonuses for target materials
        bonuses = get_terminal_yield_bonuses(term_name, material_names, yields_data)

        # Travel time
        dist_gm = None
        travel_min = None
        if args.refinery_pref == "nearest":
            dist_gm = fetch_terminal_distance(origin_id, term_id)
            time.sleep(0.3)
        if dist_gm is not None and qd_speed_gms > 0:
            travel_s = (dist_gm / qd_speed_gms) + QD_OVERHEAD_S
            travel_min = round(travel_s / 60, 1)

        # Best matching method per preference
        if args.method:
            best_method = methods_by_name.get(args.method)
            recommended_methods = [args.method] if best_method else []
        elif args.refinery_pref == "speed":
            recommended_methods = [m["name"] for m in methods_raw if m.get("rating_speed") == 3]
        elif args.refinery_pref == "economy":
            recommended_methods = [m["name"] for m in methods_raw if m.get("rating_cost") == 1]
        else:
            recommended_methods = [m["name"] for m in methods_raw if m.get("rating_yield") == 3]

        # Net yield per material (base + terminal bonus) for the preferred method category
        pref_yield_rating = {"nearest": 3, "yield": 3, "economy": 1, "speed": 1}.get(args.refinery_pref, 3)
        base_pct = BASE_YIELD_PCT[pref_yield_rating]
        net_yields = {}
        raw_ore_adjustments = {}
        for mat in material_names:
            bonus = bonuses.get(mat, 0)
            net = min(95, base_pct + bonus)  # cap at 95%
            net_yields[mat] = {"net_yield_pct": net, "terminal_bonus": bonus}
            # Adjusted raw ore needed accounting for this terminal's bonus
            slot_needed = next(s["refined_scu"] for s in slots if s["material"] == mat)
            raw_ore_adjustments[mat] = round(slot_needed / (net / 100), 3)

        score = score_refinery(
            term, bonuses, methods_raw, args.refinery_pref, travel_min, material_names
        )

        ranked_refineries.append({
            "terminal_name": term_name,
            "terminal_id": term_id,
            "system": term.get("star_system_name"),
            "location": term.get("space_station_name") or term.get("outpost_name") or term.get("orbit_name"),
            "travel_min": travel_min,
            "distance_gm": dist_gm,
            "yield_bonuses": bonuses,
            "net_yields": net_yields,
            "raw_ore_needed_at_this_terminal": raw_ore_adjustments,
            "recommended_methods": recommended_methods,
            "score": round(score, 2),
        })

    ranked_refineries.sort(key=lambda r: -r["score"])
    ranked_refineries = ranked_refineries[: args.top_refineries]

    # ── Selective refining recommendation ──
    selective = {}
    for plan in material_plans:
        econ = plan.get("economics") or {}
        worth = econ.get("worth_refining")
        mat = plan["material"]
        if args.refine_what == "all":
            selective[mat] = {"decision": "refine", "reason": "--refine-what all"}
        elif args.refine_what == "needed":
            selective[mat] = {"decision": "refine", "reason": "required for crafting"}
        else:  # selective
            if worth is True:
                selective[mat] = {"decision": "refine", "reason": econ.get("reason", "")}
            elif worth is False:
                selective[mat] = {"decision": "sell_raw", "reason": econ.get("reason", "")}
            else:
                selective[mat] = {"decision": "refine", "reason": "no price data; refine as default"}

    # ── Total trip estimate with best refinery ──
    best_ref = ranked_refineries[0] if ranked_refineries else None
    total_raw_per_scenario = {}
    if best_ref:
        for sc_label in ["worst", "middle", "best"]:
            total = 0
            for plan in material_plans:
                mat = plan["material"]
                raw_at_best = best_ref["raw_ore_needed_at_this_terminal"].get(mat)
                if raw_at_best is None:
                    # Fallback to middle yield scenario
                    raw_at_best = plan["yield_scenarios"]["medium_yield"]["raw_ore_needed_scu"]
                # Find matching trip scenario
                trip_sc = next(
                    (t for t in plan["trip_scenarios"] if t["scenario"] == sc_label), None
                )
                if trip_sc:
                    total += raw_at_best
                else:
                    total += raw_at_best
            total = round(total, 3)
            trips = trip_estimate(
                total,
                ship_cargo * 0.5  # conservative: 50% of hold is target material on average
            )
            total_raw_per_scenario[sc_label] = {
                "total_raw_scu": total,
                "trips": trips,
            }

    print(json.dumps({
        "blueprint": args.blueprint,
        "ship": args.ship,
        "ship_cargo_scu": ship_cargo,
        "location": args.location,
        "system": args.system,
        "refinery_pref": args.refinery_pref,
        "refine_what": args.refine_what,
        "materials": material_plans,
        "total_trip_estimates": total_raw_per_scenario,
        "refineries_ranked": ranked_refineries,
        "selective_refining": selective,
        "caveats": [
            "Base yield % are game approximations (±2-5%). Verify at the in-game refinery terminal.",
            "Refinery fees (~6-14% of refined value) are estimates. Check exact fee in-game before committing.",
            "Trip estimates assume target material fills the given concentration % of the full cargo hold.",
            "Prices fetched live from UEX API — community-reported, may lag actual in-game prices by up to 30 min.",
            "Quantum travel time = distance / ship QD speed + 30s overhead. Add landing/takeoff time manually.",
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
