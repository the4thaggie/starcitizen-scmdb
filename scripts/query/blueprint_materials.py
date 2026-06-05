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

    output = {
        "found": True,
        "name": match.get("productName") or match.get("tag"),
        "manufacturer": match.get("manufacturer"),
        "type": match.get("type"),
        "subtype": match.get("subtype"),
        "craft_time_seconds": tier.get("craftTimeSeconds"),
        "slots": slots_out,
        "note": "base_stats require SC Wiki API integration (not yet available)",
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
