#!/usr/bin/env python3
"""
Transforms crafting_blueprints-<version>.json into a denormalized fabricator JSON
optimized for AI consumption. Resolves faction unlock requirements from merged.json
and computes quality-to-stat tables for each material slot.

Usage:
    python3 scripts/transform/fabricator.py [<version>]

Input:  data/raw/<version>/crafting_blueprints.json
        data/raw/<version>/merged.json
Output: data/fabricator/<version>.json
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
QUALITY_CHECKPOINTS = [1, 250, 500, 750, 850, 1000]


def load_raw(version: str) -> tuple[dict, dict]:
    bp_path = REPO_ROOT / "data" / "raw" / version / "crafting_blueprints.json"
    merged_path = REPO_ROOT / "data" / "raw" / version / "merged.json"
    for p in (bp_path, merged_path):
        if not p.exists():
            sys.exit(f"ERROR: {p} not found. Run scripts/fetch/scmdb_raw.py first.")
    with open(bp_path) as f:
        bp_data = json.load(f)
    with open(merged_path) as f:
        merged = json.load(f)
    return bp_data, merged


def lerp(quality: float, q0: float, q1: float, m0: float, m1: float) -> float:
    t = (quality - q0) / (q1 - q0)
    return m0 + t * (m1 - m0)


def modifier_at(quality: int, modifiers: list) -> float:
    for m in modifiers:
        if m["startQuality"] <= quality <= m["endQuality"]:
            return lerp(quality, m["startQuality"], m["endQuality"],
                        m["modifierAtStart"], m["modifierAtEnd"])
    return 1.0


def quality_breakpoints(modifiers: list) -> list:
    return [
        {
            "quality": q,
            "modifier": round(modifier_at(q, modifiers), 4),
            "delta_pct": round((modifier_at(q, modifiers) - 1.0) * 100, 2),
        }
        for q in QUALITY_CHECKPOINTS
    ]


def build_pool_index(merged: dict) -> dict[str, dict]:
    """Map blueprint guid → {faction, pool_name, pool_size, unlock_tier, unlock_rep}."""
    factions = merged["factions"]
    bp_pools = merged["blueprintPools"]
    contracts = merged["contracts"]
    faction_rewards_pools = merged.get("factionRewardsPools", [])

    # Build pool membership: blueprint guid → pool id
    bp_to_pool: dict[str, str] = {}
    for pool_id, pool in bp_pools.items():
        for entry in pool.get("blueprints", []):
            guid = entry.get("blueprintRecord")
            if guid:
                bp_to_pool[guid] = pool_id

    # For each pool, find the contract that awards it and its standing requirement
    pool_unlock: dict[str, dict] = {}
    for contract in contracts:
        c_str = json.dumps(contract)
        for pool_id in bp_to_pool.values():
            if pool_id not in pool_unlock and pool_id in c_str:
                faction_guid = contract.get("factionGuid")
                faction_name = factions.get(faction_guid, {}).get("name") if faction_guid else None
                ms = contract.get("minStanding") or {}
                pool = bp_pools[pool_id]
                pool_unlock[pool_id] = {
                    "faction": faction_name,
                    "pool_name": pool.get("name"),
                    "pool_size": len(pool.get("blueprints", [])),
                    "pool_blueprints": [e.get("name") for e in pool.get("blueprints", [])],
                    "unlock_tier": ms.get("name"),
                    "unlock_rep": ms.get("minReputation", 0),
                }
            # Update if this contract has a higher standing requirement (find the real unlock tier)
            elif pool_id in pool_unlock and pool_id in c_str:
                ms = contract.get("minStanding") or {}
                rep = ms.get("minReputation", 0)
                if rep > pool_unlock[pool_id]["unlock_rep"]:
                    pool_unlock[pool_id]["unlock_tier"] = ms.get("name")
                    pool_unlock[pool_id]["unlock_rep"] = rep

    # Map bp guid → unlock info
    return {guid: pool_unlock.get(pid, {}) for guid, pid in bp_to_pool.items()}


def transform_blueprint(bp: dict, unlock_info: dict, dismantle_cfg: dict,
                         blacklisted_materials: set) -> dict:
    tier = bp["tiers"][0] if bp.get("tiers") else {}
    slots_out = []
    materials_needed = []

    for slot in tier.get("slots", []):
        option = slot["options"][0] if slot.get("options") else {}
        mods = slot.get("modifiers") or []
        prop_names = list(dict.fromkeys(m["propertyName"] for m in mods))
        prop = prop_names[0] if prop_names else None
        higher = (mods[-1]["modifierAtEnd"] > mods[0]["modifierAtStart"]) if mods else True

        material_name = option.get("resourceName") or option.get("itemName")
        qty = option.get("quantity")

        slots_out.append({
            "slot_name": slot["name"],
            "material": material_name,
            "material_type": option.get("type"),   # "resource" | "item"
            "quantity_scu": qty,
            "min_quality": option.get("minQuality", 1),
            "stat_affected": prop,
            "higher_is_better": higher,
            "quality_breakpoints": quality_breakpoints(mods) if mods else [],
        })
        if material_name and qty:
            materials_needed.append({"material": material_name, "quantity_scu": qty})

    # Dismantle: returns ~50% of non-blacklisted materials
    dismantlable = [
        m for m in materials_needed
        if m["material"] and m["material"] not in blacklisted_materials
    ]
    dismantle_yield = [
        {
            "material": m["material"],
            "quantity_scu": round(m["quantity_scu"] * dismantle_cfg.get("efficiency", 0.5), 4),
        }
        for m in dismantlable
    ]

    return {
        "guid": bp["guid"],
        "name": bp.get("productName") or bp.get("tag"),
        "tag": bp.get("tag"),
        "manufacturer": bp.get("manufacturer"),
        "type": bp.get("type"),
        "subtype": bp.get("subtype"),
        "gear": bp.get("gear"),
        "craft_time_seconds": tier.get("craftTimeSeconds"),
        "faction_unlock": unlock_info if unlock_info else None,
        "slots": slots_out,
        "materials_summary": materials_needed,
        "dismantle": {
            "time_seconds": dismantle_cfg.get("dismantleTimeSeconds", 15),
            "efficiency": dismantle_cfg.get("efficiency", 0.5),
            "yield": dismantle_yield,
            "blacklisted_materials": sorted(blacklisted_materials),
        },
    }


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else (REPO_ROOT / "data" / "VERSION").read_text().strip()
    if not version or version == "UNINITIALIZED":
        sys.exit("ERROR: provide version or run fetch first.")

    print(f"=== Transform: fabricator ({version}) ===")

    bp_data, merged = load_raw(version)
    bps = bp_data["blueprints"]
    print(f"  Blueprints: {len(bps)}")

    # Global dismantle config
    dismantle_cfg = bp_data.get("dismantle", {})
    blacklisted = {
        e.get("name") for e in dismantle_cfg.get("blacklistedResources", [])
    } | {
        e.get("name") for e in dismantle_cfg.get("blacklistedEntityClasses", [])
    }
    blacklisted.discard(None)

    # Build pool unlock index
    unlock_index = build_pool_index(merged)
    print(f"  Blueprint pool mappings: {len(unlock_index)}")

    blueprints_out = [
        transform_blueprint(bp, unlock_index.get(bp["guid"], {}), dismantle_cfg, blacklisted)
        for bp in bps
    ]

    # Group by type for the index
    by_type: dict[str, int] = {}
    for b in blueprints_out:
        t = b.get("type") or "other"
        by_type[t] = by_type.get(t, 0) + 1

    out = {
        "version": version,
        "count": len(blueprints_out),
        "by_type": by_type,
        "dismantle_global": {
            "efficiency": dismantle_cfg.get("efficiency", 0.5),
            "time_seconds": dismantle_cfg.get("dismantleTimeSeconds", 15),
            "blacklisted_materials": sorted(blacklisted),
            "note": "Blacklisted materials are not returned when dismantling items that used them.",
        },
        "blueprints": blueprints_out,
    }

    out_path = REPO_ROOT / "data" / "fabricator" / f"{version}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    size_kb = out_path.stat().st_size // 1024
    print(f"  → {out_path.relative_to(REPO_ROOT)}  ({size_kb} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
