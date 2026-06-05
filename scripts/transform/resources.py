#!/usr/bin/env python3
"""
Transforms mining_data-<version>.json into a denormalized resources JSON
with dual indices: locations (what can I mine here?) and materials (where do I find this?).

Usage:
    python3 scripts/transform/resources.py [<version>]

Input:  data/raw/<version>/mining_data.json
Output: data/resources/<version>.json
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

# Location types that represent ship-minable space (not FPS-only)
SHIP_MINING_LOCATION_TYPES = {"belt", "lagrange", "moon", "planet", "ring"}
SHIP_MINING_GROUP_KEYWORDS = {"ship", "space", "belt", "ring", "asteroid"}
FPS_GROUP_KEYWORDS = {"fps", "hand", "roc", "geo"}

SYSTEM_DANGER = {"Stanton": "low", "Nyx": "medium", "Pyro": "high"}
LOCATION_RISK = {
    "belt": "low", "lagrange": "low", "ring": "low",
    "moon": "low-medium", "planet": "medium",
    "station": "low", "event": "varies",
}

QUALITY_BAND_LABELS = ["F", "E", "D", "C", "B", "A", "S", "SS"]


def load_raw(version: str) -> dict:
    path = REPO_ROOT / "data" / "raw" / version / "mining_data.json"
    if not path.exists():
        sys.exit(f"ERROR: {path} not found. Run scripts/fetch/scmdb_raw.py first.")
    with open(path) as f:
        return json.load(f)


def is_ship_mining_group(group_name: str) -> bool:
    name = (group_name or "").lower()
    if any(kw in name for kw in FPS_GROUP_KEYWORDS):
        return False
    return True  # default include — filter out only known FPS groups


def format_quality_bands(raw_bands: list, boundaries: list) -> list:
    """Convert raw upper-bound array to [{label, min, max}] pairs."""
    if not raw_bands or len(raw_bands) != len(QUALITY_BAND_LABELS):
        return []
    result = []
    prev = 0
    for label, upper in zip(QUALITY_BAND_LABELS, raw_bands):
        result.append({"grade": label, "min": prev + 1 if prev > 0 else 1, "max": upper})
        prev = upper
    return result


def build_element_lookup(elements: dict, boundaries: list) -> dict:
    """Build a clean per-element summary keyed by element name."""
    lookup = {}
    for guid, el in elements.items():
        mat_name = el.get("materialName") or el.get("name", "?")
        bands = format_quality_bands(el.get("qualityBands", []), boundaries)
        lookup[mat_name] = {
            "guid": guid,
            "raw_name": el.get("name"),
            "rarity": el.get("rarity"),
            "instability": el.get("instability", 0.0),
            "resistance": el.get("resistance", 0.0),
            "scan_signature": el.get("scanSignature"),
            "quality_bands": bands,
            "practical_target": _practical_target(bands),
        }
    return lookup


def _practical_target(bands: list) -> str:
    """Return the grade label for the B band — the practical quality target."""
    b = next((b for b in bands if b["grade"] == "B"), None)
    if b:
        return f"B ({b['min']}–{b['max']}) — practical ceiling for most miners"
    return "unknown"


def resolve_location_materials(loc: dict, compositions: dict,
                                element_lookup: dict, elements_by_guid: dict) -> list:
    """Resolve all ship-mineable materials at a location with their probabilities."""
    # Collect (element_name, deposit_probability) pairs
    mat_probs: dict[str, float] = {}

    for group in loc.get("groups", []):
        if not is_ship_mining_group(group.get("groupName", "")):
            continue
        for deposit in group.get("deposits", []):
            comp_guid = deposit.get("compositionGuid")
            dep_prob = deposit.get("relativeProbability", 0.0)
            comp = compositions.get(comp_guid)
            if not comp:
                continue
            for part in comp.get("parts", []):
                el_guid = part.get("elementGuid")
                el = elements_by_guid.get(el_guid)
                if not el:
                    continue
                mat_name = el.get("materialName") or el.get("name")
                # Use deposit probability as the location-level weight
                if mat_name not in mat_probs or dep_prob > mat_probs[mat_name]:
                    mat_probs[mat_name] = dep_prob

    # Build output list, sorted by probability desc
    result = []
    for mat_name, prob in sorted(mat_probs.items(), key=lambda x: -x[1]):
        el_info = element_lookup.get(mat_name, {})
        result.append({
            "material": mat_name,
            "probability": prob,
            "rarity": el_info.get("rarity"),
            "instability": el_info.get("instability"),
            "resistance": el_info.get("resistance"),
        })
    return result


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else (REPO_ROOT / "data" / "VERSION").read_text().strip()
    if not version or version == "UNINITIALIZED":
        sys.exit("ERROR: provide version or run fetch first.")

    print(f"=== Transform: resources ({version}) ===")

    raw = load_raw(version)
    elements_raw = raw["mineableElements"]   # guid → element dict
    compositions = raw["compositions"]       # guid → composition dict
    locations_raw = raw["locations"]
    boundaries = raw.get("qualityBandBoundaries", [])
    refineries = raw.get("refineries", [])

    # Build element lookups
    elements_by_guid = elements_raw  # already keyed by guid
    element_lookup = build_element_lookup(elements_raw, boundaries)
    print(f"  Mineable elements: {len(element_lookup)}")
    print(f"  Compositions: {len(compositions)}")
    print(f"  Locations: {len(locations_raw)}")

    # --- Location index ---
    locations_out = []
    for loc in locations_raw:
        loc_type = loc.get("locationType", "unknown")
        loc_system = loc.get("system")

        # Determine mining types available
        mining_types = set()
        for group in loc.get("groups", []):
            gname = (group.get("groupName") or "").lower()
            if any(kw in gname for kw in FPS_GROUP_KEYWORDS):
                mining_types.add("fps")
            else:
                mining_types.add("ship")

        materials_at_loc = resolve_location_materials(
            loc, compositions, element_lookup, elements_by_guid
        )

        sys_danger = SYSTEM_DANGER.get(loc_system, "unknown")
        loc_risk = LOCATION_RISK.get(loc_type, "unknown")

        locations_out.append({
            "name": loc.get("locationName"),
            "system": loc_system,
            "type": loc_type,
            "system_danger": sys_danger,
            "location_risk": loc_risk,
            "mining_types": sorted(mining_types),
            "materials": materials_at_loc,
        })

    # Sort: ship-minable first, then by system danger asc
    danger_order = {"low": 0, "low-medium": 1, "medium": 2, "high": 3, "varies": 4, "unknown": 5}
    locations_out.sort(key=lambda l: (
        0 if "ship" in l["mining_types"] else 1,
        danger_order.get(l["system_danger"], 9),
        danger_order.get(l["location_risk"], 9),
    ))

    # --- Material index ---
    # For each material, find all locations where it appears
    material_index: dict[str, dict] = {}
    for loc in locations_out:
        for mat in loc.get("materials", []):
            name = mat["material"]
            if name not in material_index:
                el_info = element_lookup.get(name, {})
                material_index[name] = {
                    "name": name,
                    "rarity": el_info.get("rarity"),
                    "instability": el_info.get("instability"),
                    "resistance": el_info.get("resistance"),
                    "scan_signature": el_info.get("scan_signature"),
                    "quality_bands": el_info.get("quality_bands", []),
                    "practical_target": el_info.get("practical_target"),
                    "locations": [],
                }
            material_index[name]["locations"].append({
                "name": loc["name"],
                "system": loc["system"],
                "type": loc["type"],
                "system_danger": loc["system_danger"],
                "location_risk": loc["location_risk"],
                "probability": mat["probability"],
            })

    # Sort each material's locations by probability desc
    for mat in material_index.values():
        mat["locations"].sort(key=lambda l: -l["probability"])

    # Refinery summary
    refineries_out = [
        {"name": r.get("name"), "system": r.get("system"), "location": r.get("location")}
        for r in (refineries if isinstance(refineries, list) else [])
    ]

    out = {
        "version": version,
        "location_count": len(locations_out),
        "material_count": len(material_index),
        "locations": locations_out,
        "materials": material_index,
        "refineries": refineries_out,
    }

    out_path = REPO_ROOT / "data" / "resources" / f"{version}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    size_kb = out_path.stat().st_size // 1024
    print(f"  → {out_path.relative_to(REPO_ROOT)}  ({size_kb} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
