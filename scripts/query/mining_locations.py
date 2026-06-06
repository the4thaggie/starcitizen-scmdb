#!/usr/bin/env python3
"""
Returns ranked mining locations for a set of target materials, filtered by system
and annotated with crackability hints for the player's ship.

Usage:
    python3 scripts/query/mining_locations.py \
        --materials "Borase,Tungsten,Ouratite" \
        --system Stanton \
        --ship Prospector

Output (JSON):
    {
      "system": "Stanton",
      "ship": "Prospector",
      "materials": {
        "Borase": { rarity, instability, resistance, locations: [...], crack_assessment },
        ...
      },
      "recommended_route": [
        { stop, location, system, type, materials_here, risk, notes }
      ],
      "warnings": [...]
    }
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

# Rough crackability thresholds for stock Prospector (single Arbor MK1)
# instability >= 500 = marginal/difficult; >= 700 = very difficult; resistance >= 0.7 = hard
SHIP_CRACK_PROFILES = {
    "prospector": {"max_instability": 500, "max_resistance": 0.65, "lasers": 1, "note": "Stock Prospector — single laser, limited active modules"},
    "golem":      {"max_instability": 500, "max_resistance": 0.65, "lasers": 1, "note": "Similar to Prospector but larger cargo"},
    "mole":       {"max_instability": 700, "max_resistance": 0.75, "lasers": 3, "note": "Multi-laser, better for high-instability rocks with crew"},
    "unknown":    {"max_instability": 400, "max_resistance": 0.60, "lasers": 1, "note": "Ship unknown — conservative estimates applied"},
}

LOCATION_TYPE_RISK = {
    "belt":     "low",
    "lagrange": "low",
    "moon":     "low-medium",
    "planet":   "medium",
    "station":  "low",
    "event":    "varies",
}

SYSTEM_DANGER = {
    "Stanton": "low",
    "Nyx":     "medium",
    "Pyro":    "high",
}


def load_mining_data():
    version = (REPO_ROOT / "data" / "VERSION").read_text().strip()
    path = REPO_ROOT / "data" / "raw" / version / "mining_data.json"
    if not path.exists():
        sys.exit("ERROR: mining_data.json not found. Run scripts/fetch/scmdb_raw.py first.")
    with open(path) as f:
        return json.load(f)


def normalize(value: str | None) -> str:
    return (value or "").strip().casefold()


def material_candidates(elements: dict, needle: str, limit: int = 5) -> list[str]:
    n = normalize(needle)
    candidates = []
    seen = set()
    for el in elements.values():
        for key in ("materialName", "name"):
            name = el.get(key)
            if not name:
                continue
            if normalize(name).startswith(n) and name not in seen:
                candidates.append(name)
                seen.add(name)
                if len(candidates) >= limit:
                    return candidates
    return candidates


def crack_assessment(instability: float, resistance: float, ship_profile: dict) -> str:
    max_i = ship_profile["max_instability"]
    max_r = ship_profile["max_resistance"]
    if instability > max_i and resistance > max_r:
        return "difficult — both instability and resistance exceed ship capability; modules required"
    elif instability > max_i:
        return "marginal — high instability requires careful power management; active modules help"
    elif resistance > max_r:
        return "marginal — high resistance; may need upgraded laser or charge gadget"
    elif instability == 0 and resistance < 0:
        return "easy — low instability, negative resistance means rock cracks readily"
    else:
        return "manageable — within stock ship capability"


def find_locations_for_elements(mining_data: dict, target_element_guids: dict, system_filter: str | None) -> dict:
    compositions = mining_data["compositions"]
    locations = mining_data["locations"]

    # Map element guid -> set of composition guids
    el_to_comps = {name: set() for name in target_element_guids}
    for comp_guid, comp in compositions.items():
        for part in comp.get("parts", []):
            for name, el_guid in target_element_guids.items():
                if part.get("elementGuid") == el_guid:
                    el_to_comps[name].add(comp_guid)

    # Find locations for each element
    result = {}
    for name, comp_guids in el_to_comps.items():
        locs = []
        for loc in locations:
            if loc.get("locationType") == "event":
                continue
            loc_system = loc.get("system")
            if system_filter and normalize(loc_system) != normalize(system_filter):
                continue
            for group in loc.get("groups", []):
                if "fps" in (group.get("groupName") or "").lower():
                    continue  # skip FPS/hand-mining groups
                for dep in group.get("deposits", []):
                    if dep.get("compositionGuid") in comp_guids:
                        prob = dep.get("relativeProbability", 0)
                        locs.append({
                            "name": loc.get("locationName"),
                            "system": loc_system,
                            "type": loc.get("locationType"),
                            "probability": prob,
                        })
        # Deduplicate: keep max probability per location
        by_name = {}
        for l in locs:
            k = l["name"]
            if k not in by_name or l["probability"] > by_name[k]["probability"]:
                by_name[k] = l
        result[name] = sorted(by_name.values(), key=lambda x: -x["probability"])

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--materials", required=True, help="Comma-separated material names, e.g. Borase,Tungsten,Ouratite")
    parser.add_argument("--system", default=None, help="Filter to system: Stanton | Pyro | Nyx")
    parser.add_argument("--ship", default="unknown")
    args = parser.parse_args()

    mining_data = load_mining_data()
    elements = mining_data["mineableElements"]

    ship_key = args.ship.lower().strip()
    ship_profile = SHIP_CRACK_PROFILES.get(ship_key, SHIP_CRACK_PROFILES["unknown"])

    target_names = [m.strip() for m in args.materials.split(",")]

    # Resolve material names to element guids
    target_element_guids = {}
    not_found = []
    for name in target_names:
        match = next(
            (guid for guid, el in elements.items()
             if normalize(name) == normalize(el.get("materialName")) or
                normalize(name) == normalize(el.get("name"))),
            None
        )
        if match:
            target_element_guids[name] = match
        else:
            not_found.append(name)

    locations_by_material = find_locations_for_elements(mining_data, target_element_guids, args.system)

    # Build material summaries
    material_summaries = {}
    for name in target_names:
        if name in not_found:
            material_summaries[name] = {
                "error": "not found in mining data",
                "candidates": material_candidates(elements, name),
                "hint": "Use the exact material name from mining data.",
            }
            continue
        el_guid = target_element_guids[name]
        el = elements[el_guid]
        instability = el.get("instability", 0)
        resistance = el.get("resistance", 0)
        locs = locations_by_material.get(name, [])
        material_summaries[name] = {
            "rarity": el.get("rarity"),
            "instability": instability,
            "resistance": resistance,
            "crack_assessment": crack_assessment(instability, resistance, ship_profile),
            "location_count": len(locs),
            "top_locations": [
                {
                    "name": l["name"],
                    "system": l["system"],
                    "type": l["type"],
                    "system_danger": SYSTEM_DANGER.get(l["system"], "unknown"),
                    "location_risk": LOCATION_TYPE_RISK.get(l["type"], "unknown"),
                }
                for l in locs[:5]
            ],
        }

    # Build recommended route: find locations that cover multiple materials
    all_locs: dict[str, dict] = {}
    for name, locs in locations_by_material.items():
        for l in locs:
            k = l["name"]
            if k not in all_locs:
                all_locs[k] = {"name": k, "system": l["system"], "type": l["type"],
                                "materials": [], "max_prob": 0}
            all_locs[k]["materials"].append(name)
            all_locs[k]["max_prob"] = max(all_locs[k]["max_prob"], l["probability"])

    # Score: prefer locations covering more materials, then higher probability
    scored = sorted(all_locs.values(), key=lambda l: (-len(l["materials"]), -l["max_prob"]))

    # Build a minimal route covering all materials
    route = []
    covered = set()
    for loc in scored:
        new = [m for m in loc["materials"] if m not in covered]
        if not new:
            continue
        sys_danger = SYSTEM_DANGER.get(loc["system"], "unknown")
        loc_risk = LOCATION_TYPE_RISK.get(loc["type"], "unknown")
        overall_risk = "high" if sys_danger == "high" else loc_risk

        notes_parts = []
        for m in loc["materials"]:
            assess = material_summaries.get(m, {}).get("crack_assessment", "")
            if "difficult" in assess or "marginal" in assess:
                notes_parts.append(f"{m}: {assess}")

        route.append({
            "stop": len(route) + 1,
            "location": loc["name"],
            "system": loc["system"],
            "type": loc["type"],
            "system_danger": sys_danger,
            "overall_risk": overall_risk,
            "materials_here": loc["materials"],
            "new_materials_collected": new,
            "notes": notes_parts if notes_parts else ["All materials here within ship capability"],
        })
        covered.update(new)
        if covered >= set(target_names) - set(not_found):
            break

    warnings = []
    if not_found:
        warnings.append(f"Materials not found in mining data: {not_found}")
    if any("difficult" in (material_summaries.get(n, {}).get("crack_assessment", "")) for n in target_names):
        warnings.append(
            f"Some materials exceed stock {args.ship} crack capability. "
            "Upgraded laser or active modules (e.g. Surge/Vaux) may be required."
        )
    if not args.system:
        warnings.append("No system specified — showing all systems. Use --system to filter by your location.")

    print(json.dumps({
        "system_filter": args.system or "all",
        "ship": args.ship,
        "ship_profile_note": ship_profile["note"],
        "materials": material_summaries,
        "recommended_route": route,
        "warnings": warnings,
    }, indent=2))


if __name__ == "__main__":
    main()
