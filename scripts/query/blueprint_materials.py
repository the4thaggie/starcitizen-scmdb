#!/usr/bin/env python3
"""
Returns crafting material requirements and quality-to-stat tables for a blueprint.
The agent calls this after blueprint_unlock.py when the user needs to know what to mine/buy.

Usage:
    python3 scripts/query/blueprint_materials.py --name "Yeager"

Output (JSON):
    {
      "name": "Yeager",
      "craft_time_seconds": 1230,
      "slots": [
        {
          "slot_name": "Case",
          "material": "Borase",
          "quantity_scu": 1.24,
          "min_quality": 1,
          "stat_affected": "Integrity",
          "quality_breakpoints": [
            {"quality": 1,    "modifier": 0.80, "delta_pct": -20.0},
            {"quality": 500,  "modifier": 1.00, "delta_pct":   0.0},
            {"quality": 750,  "modifier": 1.10, "delta_pct":  +9.98},
            {"quality": 1000, "modifier": 1.20, "delta_pct": +20.0}
          ],
          "higher_is_better": true
        },
        ...
      ]
    }
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

QUALITY_CHECKPOINTS = [1, 250, 500, 750, 850, 1000]


def load_blueprints():
    version = (REPO_ROOT / "data" / "VERSION").read_text().strip()
    bp_path = REPO_ROOT / "data" / "raw" / version / "crafting_blueprints.json"
    if not bp_path.exists():
        sys.exit("ERROR: Run scripts/update_cache.sh first.")
    with open(bp_path) as f:
        return json.load(f)


def load_wiki_index() -> dict:
    """Load all wiki item files into a single name-keyed lookup."""
    index = {}
    for fname in ("quantum_drives.json", "mining_lasers.json"):
        path = REPO_ROOT / "data" / "wiki" / fname
        if path.exists():
            with open(path) as f:
                index.update(json.load(f))
    return index


def lerp_modifier(quality, modifiers):
    for m in modifiers:
        if m["startQuality"] <= quality <= m["endQuality"]:
            t = (quality - m["startQuality"]) / (m["endQuality"] - m["startQuality"])
            return m["modifierAtStart"] + t * (m["modifierAtEnd"] - m["modifierAtStart"])
    return 1.0


def quality_breakpoints(modifiers):
    points = []
    for q in QUALITY_CHECKPOINTS:
        mod = lerp_modifier(q, modifiers)
        points.append({
            "quality": q,
            "modifier": round(mod, 4),
            "delta_pct": round((mod - 1.0) * 100, 2),
        })
    return points


def higher_is_better(modifiers):
    """True if higher quality = higher modifier (stat goes up). False if inverse (like fuel burn)."""
    if not modifiers:
        return True
    return modifiers[-1]["modifierAtEnd"] > modifiers[0]["modifierAtStart"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Blueprint product name")
    args = parser.parse_args()

    bp_data = load_blueprints()
    bps = bp_data["blueprints"]
    wiki = load_wiki_index()

    match = next(
        (b for b in bps if (b.get("productName") or "").lower() == args.name.lower()),
        None
    )
    if not match:
        # Partial match
        match = next(
            (b for b in bps if args.name.lower() in (b.get("productName") or "").lower()),
            None
        )
    if not match:
        print(json.dumps({"found": False, "name": args.name}))
        return

    tier = match["tiers"][0] if match.get("tiers") else {}
    slots_out = []
    for slot in tier.get("slots", []):
        option = slot["options"][0] if slot.get("options") else {}
        mods = slot.get("modifiers") or []

        # Get unique property name
        prop_names = list(dict.fromkeys(m["propertyName"] for m in mods))
        prop = prop_names[0] if prop_names else None

        slot_out = {
            "slot_name": slot["name"],
            "material": option.get("resourceName") or option.get("itemName"),
            "material_type": option.get("type"),
            "quantity_scu": option.get("quantity"),
            "min_quality": option.get("minQuality", 1),
            "stat_affected": prop,
            "higher_is_better": higher_is_better(mods),
            "quality_breakpoints": quality_breakpoints(mods) if mods else [],
        }
        slots_out.append(slot_out)

    bp_name = match.get("productName") or match.get("tag")

    # Enrich with SC Wiki base stats if available
    wiki_entry = wiki.get(bp_name, {})
    base_stats = None
    item_class = wiki_entry.get("class")
    item_grade = wiki_entry.get("grade")

    if wiki_entry:
        # Build base stats with computed values at each quality checkpoint
        perf = wiki_entry.get("performance", {})
        bs = wiki_entry.get("base_stats", {})
        base_stats = {
            "grade": item_grade,
            "class": item_class,
            "mass_kg": wiki_entry.get("mass_kg"),
            "health_hp": bs.get("health_hp"),
            "power_draw": bs.get("power_draw"),
            "em_signature": bs.get("em_signature"),
            "repair_time_s": bs.get("repair_time_s"),
        }
        # Add type-specific performance stats
        if wiki_entry.get("type") == "QuantumDrive" or perf.get("drive_speed_mms"):
            base_stats["performance"] = {
                "drive_speed_mms": perf.get("drive_speed_mms"),
                "drive_speed_formatted": perf.get("drive_speed_formatted"),
                "cooldown_s": perf.get("cooldown_s"),
                "spool_up_s": perf.get("spool_up_s"),
                "fuel_per_jump": perf.get("fuel_per_jump"),
                "fuel_efficiency": perf.get("fuel_efficiency"),
                "travel_time_10gm": perf.get("travel_time_10gm"),
            }
        # Annotate each slot's quality_breakpoints with absolute stat values
        for slot in slots_out:
            prop = slot.get("stat_affected")
            if not prop or not base_stats.get("performance"):
                continue
            # Map stat name to base value
            stat_map = {
                "Integrity": base_stats.get("health_hp"),
                "Quantum Speed": perf.get("drive_speed_mms"),
                "Quantum Fuel Burn": perf.get("fuel_per_jump"),
            }
            base_val = stat_map.get(prop)
            if base_val:
                unit_map = {
                    "Integrity": "HP",
                    "Quantum Speed": "Mm/s",
                    "Quantum Fuel Burn": "fuel/jump",
                }
                for bp_point in slot["quality_breakpoints"]:
                    bp_point["absolute_value"] = round(base_val * bp_point["modifier"], 4)
                    bp_point["unit"] = unit_map.get(prop, "")

    output = {
        "found": True,
        "name": bp_name,
        "manufacturer": match.get("manufacturer"),
        "type": match.get("type"),
        "subtype": match.get("subtype"),
        "grade": item_grade,
        "class": item_class,
        "craft_time_seconds": tier.get("craftTimeSeconds"),
        "base_stats": base_stats,
        "slots": slots_out,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
