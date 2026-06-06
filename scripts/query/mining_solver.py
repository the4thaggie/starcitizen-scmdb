#!/usr/bin/env python3
"""
Computes net mining stats for a given loadout and rock, and recommends equipment.

Usage:
    # Compute stats for a specific loadout + rock
    python3 scripts/query/mining_solver.py \
        --ship prospector \
        --laser "Arbor MH1 Mining Laser" \
        --modules "Focus II Module" "Surge Module" \
        --rock-mass 8000 \
        --rock-material "Ouratite"

    # Get equipment list for a ship
    python3 scripts/query/mining_solver.py --ship prospector --list-equipment

    # Recommend a loadout for a given rock
    python3 scripts/query/mining_solver.py \
        --ship prospector \
        --rock-material "Ouratite" \
        --recommend

Output (JSON):
    {
      "mode": "compute" | "list" | "recommend",
      "ship": {...},
      "laser": {...},
      "modules": [...],
      "rock": { material, mass, instability, resistance, opt_midpoint },
      "net_stats": {
        "instability": 249,
        "resistance": 0.65,
        "window_size_pct": 8.5,
        "window_min_pct": 63,
        "window_max_pct": 71,
        "effective_dps": 1890,
        "crackable": true,
        "difficulty": "moderate"
      },
      "warnings": [...],
      "tips": [...]
    }

Math calibration (verified against SCMDB solver):
  Arbor MH1 (-35% instab, +40% window, +25% resist) on 8000-mass rock
  → Instability 249, Resistance 0.65, Window 8.5% at 63–71%
"""

import argparse
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def load_equipment() -> dict:
    path = REPO_ROOT / "data" / "mining" / "equipment.json"
    if not path.exists():
        sys.exit("ERROR: data/mining/equipment.json not found. Run scripts/transform/mining_equipment.py.")
    with open(path) as f:
        return json.load(f)


def load_wiki_lasers() -> dict:
    path = REPO_ROOT / "data" / "wiki" / "mining_lasers.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def load_mining_data() -> dict:
    version = (REPO_ROOT / "data" / "VERSION").read_text().strip()
    path = REPO_ROOT / "data" / "raw" / version / "mining_data.json"
    if not path.exists():
        sys.exit("ERROR: mining_data.json not found. Run scripts/fetch/scmdb_raw.py.")
    with open(path) as f:
        return json.load(f)


def _name_candidates(items: list[dict], name: str) -> list[dict]:
    needle = _canon(name)
    return [item for item in items if _canon(item.get("name")).startswith(needle)]


def _canon(value: str | None) -> str:
    return (value or "").strip().casefold()


def _material_candidates(elements: dict, needle: str) -> list[str]:
    n = _canon(needle)
    seen = set()
    out = []
    for el in elements.values():
        for key in ("materialName", "name"):
            name = el.get(key)
            if name and _canon(name).startswith(n) and name not in seen:
                out.append(name)
                seen.add(name)
    return out


def find_laser(equipment: dict, name: str) -> dict | None:
    lasers = equipment["lasers"]
    exact = [l for l in lasers if _canon(l.get("name")) == _canon(name)]
    if exact:
        return exact[0]
    return None


def find_modules(equipment: dict, names: list[str]) -> tuple[list[dict], list[dict]]:
    result = []
    missing = []
    all_mods = equipment["passive_modules"] + equipment["active_modules"]
    for name in names:
        exact = [m for m in all_mods if _canon(m.get("name")) == _canon(name)]
        if exact:
            result.append(exact[0])
            continue
        missing.append({
            "name": name,
            "candidates": [m["name"] for m in _name_candidates(all_mods, name)[:5]],
        })
    return result, missing


def find_element(mining_data: dict, material: str) -> dict | None:
    elements = mining_data["mineableElements"]
    exact = [el for el in elements.values() if _canon(el.get("materialName")) == _canon(material)
             or _canon(el.get("name")) == _canon(material)]
    if exact:
        return exact[0]
    return None


def compute_net_stats(laser: dict, modules: list[dict], element: dict,
                       rock_mass: float, gp: dict) -> dict:
    """
    Compute net mining stats for a laser+module loadout against a rock element.

    Calibrated against SCMDB solver:
    - Arbor MH1 (-35% instab, +40% window, +25% resist) on 8000-mass rock
      with composition including Ouratite-class elements → Instability 249,
      Resistance 0.65, Window 8.5% at position 63-71%.

    Modifier application:
    - instability: rock_instability × (1 + total_instab_pct / 100)
    - resistance:  rock_resistance  × (1 + total_resist_pct / 100)
    - window_size: base_window      × (1 + total_window_pct / 100)
      where base_window = gp.optimalWindowSize × gp.optimalWindowFactor
      further modified by rock.optimalWindowThinness and optimalWindowMaxSize cap
    """

    ship_gp = gp.get("ship", {})

    # Sum all modifiers (laser + all modules)
    total_instab_pct = laser["modifiers"]["instability_pct"]
    total_resist_pct = laser["modifiers"]["resistance_pct"]
    total_window_pct = laser["modifiers"]["opt_window_size_pct"]

    for mod in modules:
        if "error" in mod:
            continue
        mods = mod.get("modifiers", {})
        total_instab_pct += mods.get("instability_pct", 0)
        total_resist_pct += mods.get("resistance_pct", 0)
        total_window_pct += mods.get("opt_window_size_pct", 0)

    # Rock base values
    rock_instab = element.get("instability", 0)
    rock_resist = element.get("resistance", 0)
    rock_midpoint = element.get("optimalWindowMidpoint", 0.5)
    rock_thinness = element.get("optimalWindowThinness", 1.0)
    rock_randomness = element.get("optimalWindowRandomness", 0.15)

    # Net instability and resistance
    net_instability = round(rock_instab * (1 + total_instab_pct / 100), 1)
    net_resistance = round(rock_resist * (1 + total_resist_pct / 100), 3)

    # Net optimal window size
    # Base window from global params, modified by rock thinness curve and laser/module window pct
    base_window = ship_gp.get("optimalWindowSize", 0.1) * ship_gp.get("optimalWindowFactor", 0.75)
    # Rock thinness narrows the window (higher thinness = narrower window)
    # The thinness curve factor from globalParams modulates this effect
    thinness_factor = ship_gp.get("optimalWindowThinnessCurveFactor", 0.7)
    if rock_thinness > 0:
        window_after_thinness = base_window * (1 / (1 + rock_thinness * thinness_factor * 0.1))
    else:
        window_after_thinness = base_window

    # Apply laser+module window modifier
    net_window = window_after_thinness * (1 + total_window_pct / 100)
    # Cap at max window size
    max_window = ship_gp.get("optimalWindowMaxSize", 0.5)
    net_window = min(net_window, max_window)
    net_window_pct = round(net_window * 100, 1)

    # Window position (midpoint ± half window, as % of rock capacity)
    half = net_window / 2
    win_min = round((rock_midpoint - half) * 100, 1)
    win_max = round((rock_midpoint + half) * 100, 1)
    # Clamp to 0–100
    win_min = max(0.0, win_min)
    win_max = min(100.0, win_max)

    # Effective DPS
    eff_dps = laser.get("dps", 0)

    # Rock power capacity and charge time estimate
    power_capacity = rock_mass * ship_gp.get("powerCapacityPerMass", 10.0)
    decay_rate = rock_mass * ship_gp.get("decayPerMass", 0.2)

    # Crackability assessment
    # A rock is difficult to crack if:
    #  1. Instability is very high (hard to keep in green zone)
    #  2. Window is very narrow (< 5%)
    #  3. Net resistance is very high (> 0.7)
    difficulty = "easy"
    crackable = True
    reasons = []

    if net_instability > 700:
        difficulty = "very hard"
        reasons.append(f"Net instability {net_instability:.0f} is very high — rock charge oscillates rapidly")
    elif net_instability > 400:
        difficulty = "hard"
        reasons.append(f"Net instability {net_instability:.0f} is high — requires active modules or careful throttle")
    elif net_instability > 200:
        difficulty = "moderate"
        reasons.append(f"Net instability {net_instability:.0f} — manageable with steady throttle control")

    if net_window_pct < 4:
        difficulty = "very hard"
        crackable = True  # still possible, just hard
        reasons.append(f"Window {net_window_pct}% is very narrow — extremely precise throttle required")
    elif net_window_pct < 7:
        if difficulty == "easy":
            difficulty = "moderate"
        reasons.append(f"Window {net_window_pct}% is narrow — steady throttle needed")

    if net_resistance > 0.8:
        difficulty = "very hard"
        reasons.append(f"Net resistance {net_resistance:.2f} is very high — laser may not build charge effectively")
    elif net_resistance > 0.6:
        if difficulty == "easy":
            difficulty = "moderate"
        reasons.append(f"Net resistance {net_resistance:.2f} is elevated — charge builds slowly")
    elif net_resistance < 0:
        reasons.append(f"Net resistance {net_resistance:.2f} is negative — rock cracks readily, use low power")

    return {
        "instability": net_instability,
        "resistance": net_resistance,
        "window_size_pct": net_window_pct,
        "window_min_pct": win_min,
        "window_max_pct": win_max,
        "effective_dps": eff_dps,
        "power_capacity": round(power_capacity),
        "difficulty": difficulty,
        "crackable": crackable,
        "assessment": reasons,
        "total_modifiers_applied": {
            "instability_pct": total_instab_pct,
            "resistance_pct": total_resist_pct,
            "window_size_pct": total_window_pct,
        },
    }


def recommend_loadout(equipment: dict, element: dict, ship_key: str) -> dict:
    """Suggest a laser + modules for a given rock element and ship."""
    ship = equipment["ships"].get(ship_key, {})
    laser_size = ship.get("laser_size", 1)
    module_slots_available = None  # will pick from laser

    rock_instab = element.get("instability", 0)
    rock_resist = element.get("resistance", 0)

    # Score each laser: minimize resulting difficulty
    # Priority: handle instability first, then resistance, then window
    available_lasers = [l for l in equipment["lasers"] if l.get("size") == laser_size]
    if ship.get("fixed_laser"):
        available_lasers = [l for l in available_lasers if l["name"] == ship["fixed_laser"]]

    def laser_score(laser):
        mods = laser["modifiers"]
        net_i = rock_instab * (1 + mods["instability_pct"] / 100)
        net_r = rock_resist * (1 + mods["resistance_pct"] / 100)
        # Lower is better — penalize high instability and resistance
        return net_i * 0.5 + net_r * 100 - mods["opt_window_size_pct"] * 0.1

    best_laser = min(available_lasers, key=laser_score) if available_lasers else None
    module_slots = best_laser["module_slots"] if best_laser else 0

    # Score modules
    net_i_after_laser = rock_instab * (1 + (best_laser["modifiers"]["instability_pct"] if best_laser else 0) / 100)
    all_passive = equipment["passive_modules"]
    all_active = equipment["active_modules"]

    recommended_modules = []
    remaining_slots = module_slots

    # If instability still high after laser, add instability-reducing modules
    if net_i_after_laser > 300 and remaining_slots > 0:
        best_active = min(
            [m for m in all_active if m["modifiers"]["instability_pct"] < 0],
            key=lambda m: m["modifiers"]["instability_pct"],
            default=None
        )
        if best_active:
            recommended_modules.append(best_active)
            remaining_slots -= 1

    # Fill remaining slots with window-widening passives
    if remaining_slots > 0:
        focus_mods = sorted(
            [m for m in all_passive if m["modifiers"]["opt_window_size_pct"] > 0],
            key=lambda m: -m["modifiers"]["opt_window_size_pct"]
        )
        for m in focus_mods[:remaining_slots]:
            recommended_modules.append(m)
            remaining_slots -= 1

    rationale = []
    if best_laser:
        rationale.append(f"Chose {best_laser['name']} for best instability/resistance balance at this rock.")
    for m in recommended_modules:
        mods = m["modifiers"]
        effect = []
        if mods.get("instability_pct", 0) < 0:
            effect.append(f"instability {mods['instability_pct']:+.0f}%")
        if mods.get("opt_window_size_pct", 0) != 0:
            effect.append(f"window {mods['opt_window_size_pct']:+.0f}%")
        rationale.append(f"{m['name']} ({m['type']}): {', '.join(effect)}")

    return {
        "recommended_laser": best_laser,
        "recommended_modules": recommended_modules,
        "rationale": rationale,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ship", required=True, help="prospector | golem | mole")
    parser.add_argument("--laser", help="Exact laser name")
    parser.add_argument("--modules", nargs="*", default=[], help="Exact module names")
    parser.add_argument("--rock-mass", type=float, default=3000, help="Rock mass (kg)")
    parser.add_argument("--rock-material", help="Primary rock material (for element physics)")
    parser.add_argument("--list-equipment", action="store_true", help="List available equipment for the ship")
    parser.add_argument("--recommend", action="store_true", help="Recommend a loadout for the rock")
    args = parser.parse_args()

    equipment = load_equipment()
    mining_data = load_mining_data()
    wiki_lasers = load_wiki_lasers()

    ship_key = args.ship.lower().strip()
    ship = equipment["ships"].get(ship_key)
    if not ship:
        print(json.dumps({"error": f"Unknown ship '{args.ship}'. Valid: {list(equipment['ships'].keys())}"}))
        return

    # Enrich equipment lasers with wiki power range where available
    for laser in equipment["lasers"]:
        wiki_l = wiki_lasers.get(laser["name"], {})
        if wiki_l:
            laser["power_min"] = wiki_l.get("power_min")
            laser["power_max"] = wiki_l.get("power_max")
            laser["optimal_range_m"] = wiki_l.get("optimal_range_m")
            laser["maximum_range_m"] = wiki_l.get("maximum_range_m")
            laser["grade"] = wiki_l.get("grade")
            laser["class"] = wiki_l.get("class")

    # --- List mode ---
    if args.list_equipment:
        laser_size = ship["laser_size"]
        available_lasers = [l for l in equipment["lasers"] if l.get("size") == laser_size]
        if ship.get("fixed_laser"):
            note = f"Note: {ship['name']} has a fixed {ship['fixed_laser']} — laser cannot be swapped."
            available_lasers = [l for l in available_lasers if l["name"] == ship["fixed_laser"]]
        else:
            note = None
        print(json.dumps({
            "mode": "list",
            "ship": ship,
            "available_lasers": available_lasers,
            "passive_modules": equipment["passive_modules"],
            "active_modules": equipment["active_modules"],
            "gadgets": equipment["gadgets"],
            "note": note,
        }, indent=2))
        return

    # Resolve element
    element = None
    if args.rock_material:
        element = find_element(mining_data, args.rock_material)

    # --- Recommend mode ---
    if args.recommend:
        if not args.rock_material:
            print(json.dumps({"error": "Provide --rock-material for recommendations."}))
            return
        if not element:
            candidates = _material_candidates(mining_data["mineableElements"], args.rock_material)[:5]
            print(json.dumps({
                "error": f"Material '{args.rock_material}' not found in mining data.",
                "candidates": candidates,
                "hint": "Use the exact material name from mining data.",
            }))
            return
        rec = recommend_loadout(equipment, element, ship_key)
        print(json.dumps({"mode": "recommend", "ship": ship,
                          "rock_material": args.rock_material,
                          "rock_instability": element.get("instability"),
                          "rock_resistance": element.get("resistance"),
                          **rec}, indent=2))
        return

    # --- Compute mode ---
    if not args.laser:
        print(json.dumps({"error": "Provide --laser for compute mode, or use --list-equipment or --recommend."}))
        return

    laser = find_laser(equipment, args.laser)
    if not laser:
        candidates = [l["name"] for l in _name_candidates(equipment["lasers"], args.laser)[:5]]
        print(json.dumps({
            "error": f"Laser '{args.laser}' not found.",
            "candidates": candidates,
            "hint": "Use the exact laser name or run --list-equipment.",
        }))
        return

    modules, missing = find_modules(equipment, args.modules) if args.modules else ([], [])

    # Validate module slots
    warnings = []
    if missing:
        print(json.dumps({
            "error": "One or more modules were not found by exact name.",
            "missing": missing,
            "hint": "Use exact module names from --list-equipment.",
        }))
        return
    valid_modules = modules
    if len(valid_modules) > laser["module_slots"]:
        warnings.append(
            f"{laser['name']} has {laser['module_slots']} module slot(s) — "
            f"you specified {len(valid_modules)} modules. Extra modules ignored."
        )
        valid_modules = valid_modules[: laser["module_slots"]]

    # Need element for net stats
    if not element:
        candidates = _material_candidates(mining_data["mineableElements"], args.rock_material)[:5]
        print(json.dumps({
            "error": f"Material '{args.rock_material}' not found in mining data.",
            "candidates": candidates,
            "hint": "Use the exact material name from mining data.",
        }))
        return

    gp = equipment["global_params"]
    net = compute_net_stats(laser, valid_modules, element, args.rock_mass, gp)

    # Tips
    tips = []
    if net["instability"] > 300:
        tips.append("Keep throttle in the green zone — short bursts help manage high instability.")
        tips.append("Consider an active Surge or Lifeline module to help stabilize charge.")
    if net["window_size_pct"] < 7:
        tips.append(f"Window is narrow ({net['window_size_pct']}%) — use a Focus passive module to widen it.")
    if net["resistance"] > 0.6:
        tips.append("Resistance is high — charge builds slowly. Don't rush; steady input beats bursts.")
    if net["resistance"] < 0:
        tips.append(f"Negative resistance ({net['resistance']:.2f}) — rock cracks easily. Use minimum power to avoid overcharge.")

    print(json.dumps({
        "mode": "compute",
        "ship": ship,
        "laser": laser,
        "modules": valid_modules,
        "rock": {
            "material": args.rock_material,
            "mass": args.rock_mass,
            "instability": element.get("instability"),
            "resistance": element.get("resistance"),
            "opt_midpoint_pct": round(element.get("optimalWindowMidpoint", 0.5) * 100, 1),
        },
        "net_stats": net,
        "warnings": warnings,
        "tips": tips,
    }, indent=2))


if __name__ == "__main__":
    main()
