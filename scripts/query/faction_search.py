#!/usr/bin/env python3
"""
Finds factions relevant to the user's goal and summarizes what each offers.
The agent calls this when the user doesn't specify a faction — before mission_grind_plan.py.

Usage:
    # Find factions that unlock a specific blueprint type
    python3 scripts/query/faction_search.py --blueprint-type quantumdrive --size 2

    # Find factions active in a system
    python3 scripts/query/faction_search.py --system Stanton

    # Find factions offering a specific mission type
    python3 scripts/query/faction_search.py --mission-type Delivery --system Stanton

    # Find factions by name keyword
    python3 scripts/query/faction_search.py --name "ling"

    # Show all factions with blueprint rewards (most common agent use-case)
    python3 scripts/query/faction_search.py --has-blueprints

Output (JSON):
    {
      "query": { ...args... },
      "count": 3,
      "factions": [
        {
          "name": "Covalex",
          "systems": ["Stanton", "Pyro", "Nyx"],
          "mission_types": ["Delivery", "Hauling", "Recovery"],
          "min_entry_tier": "Trainee",
          "min_entry_rep": 0,
          "max_tier": "Master",
          "max_tier_rep": 237750,
          "tier_count": 11,
          "mission_count": 48,
          "blueprint_pools": [
            {
              "pool_name": "BP_REWARDS_CovalexSuper",
              "blueprints": ["VK-00", "Siren", "XL-1", "Yeager", ...],
              "unlock_tier": "Master",
              "unlock_rep": 237750
            }
          ],
          "has_blueprints": true
        },
        ...
      ]
    }
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def load_data():
    version = (REPO_ROOT / "data" / "VERSION").read_text().strip()
    missions_path = REPO_ROOT / "data" / "missions" / f"{version}.json"
    bp_path = REPO_ROOT / "data" / "raw" / version / "crafting_blueprints.json"
    merged_path = REPO_ROOT / "data" / "raw" / version / "merged.json"

    if not missions_path.exists():
        sys.exit("ERROR: Run scripts/update_cache.sh first.")

    with open(missions_path) as f:
        missions_data = json.load(f)
    with open(merged_path) as f:
        merged = json.load(f)

    bp_data = None
    if bp_path.exists():
        with open(bp_path) as f:
            bp_data = json.load(f)

    return missions_data["missions"], merged, bp_data


def build_faction_index(missions: list, merged: dict, bp_data: dict | None) -> dict:
    """Build a summary of each faction from mission data."""
    factions_raw = merged.get("factions", {})
    bp_pools = merged.get("blueprintPools", {})
    contracts = merged.get("contracts", [])

    # Map blueprint guid -> product name (if bp_data available)
    bp_name_map = {}
    if bp_data:
        for b in bp_data.get("blueprints", []):
            bp_name_map[b["guid"]] = {
                "name": b.get("productName") or b.get("tag"),
                "type": b.get("type"),
                "subtype": b.get("subtype"),
                "manufacturer": b.get("manufacturer"),
            }

    # Build per-faction summary from denormalized missions
    faction_index = {}
    for m in missions:
        faction = m.get("faction")
        if not faction:
            continue

        if faction not in faction_index:
            faction_index[faction] = {
                "name": faction,
                "systems": set(),
                "mission_types": set(),
                "tiers": {},          # tier_name -> min_rep
                "mission_count": 0,
            }

        fi = faction_index[faction]
        fi["mission_count"] += 1
        for sys in (m.get("systems") or []):
            fi["systems"].add(sys)
        if m.get("missionType"):
            fi["mission_types"].add(m["missionType"])
        ms = m.get("minStanding")
        if ms and ms.get("name"):
            fi["tiers"][ms["name"]] = ms.get("minReputation", 0)

    # Find blueprint pools accessible per faction
    # Need to map faction guid -> faction name and then pool -> contract -> faction
    faction_guid_to_name = {guid: f.get("name") for guid, f in factions_raw.items()}

    # For each pool, find which contracts award it and at what tier
    pool_to_faction_unlock = {}
    for contract in contracts:
        c_str = json.dumps(contract)
        for pool_id, pool in bp_pools.items():
            if pool_id in c_str:
                faction_guid = contract.get("factionGuid")
                faction_name = faction_guid_to_name.get(faction_guid)
                ms = contract.get("minStanding") or {}
                tier = ms.get("name")
                rep = ms.get("minReputation", 0)
                if pool_id not in pool_to_faction_unlock:
                    pool_to_faction_unlock[pool_id] = {
                        "pool_name": pool.get("name"),
                        "faction": faction_name,
                        "unlock_tier": tier,
                        "unlock_rep": rep,
                        "blueprints": [],
                    }
                # Update with highest-rep entry (the unlock requirement)
                if rep > pool_to_faction_unlock[pool_id]["unlock_rep"]:
                    pool_to_faction_unlock[pool_id]["unlock_tier"] = tier
                    pool_to_faction_unlock[pool_id]["unlock_rep"] = rep

    # Resolve blueprint names and sizes in pools
    for pool_id, info in pool_to_faction_unlock.items():
        pool = bp_pools.get(pool_id, {})
        blueprints_info = []
        blueprint_types = set()
        for entry in pool.get("blueprints", []):
            bp_rec = entry.get("blueprintRecord")
            bp_info = bp_name_map.get(bp_rec, {})
            name = bp_info.get("name", "?")
            subtype = bp_info.get("subtype", "unknown")
            bptype = bp_info.get("type", "unknown")
            blueprints_info.append({"name": name, "size": subtype, "type": bptype})
            if bptype:
                blueprint_types.add(bptype)
        info["blueprints"] = blueprints_info
        info["blueprint_types"] = list(blueprint_types)

    # Attach pools to factions
    for pool_id, info in pool_to_faction_unlock.items():
        faction_name = info.get("faction")
        if faction_name and faction_name in faction_index:
            faction_index[faction_name].setdefault("blueprint_pools", []).append(info)

    # Finalize
    result = {}
    for name, fi in faction_index.items():
        tiers_sorted = sorted(fi["tiers"].items(), key=lambda x: x[1])
        result[name] = {
            "name": name,
            "systems": sorted(fi["systems"]),
            "mission_types": sorted(fi["mission_types"]),
            "mission_count": fi["mission_count"],
            "min_entry_tier": tiers_sorted[0][0] if tiers_sorted else None,
            "min_entry_rep": tiers_sorted[0][1] if tiers_sorted else 0,
            "max_tier": tiers_sorted[-1][0] if tiers_sorted else None,
            "max_tier_rep": tiers_sorted[-1][1] if tiers_sorted else 0,
            "tier_count": len(tiers_sorted),
            "blueprint_pools": fi.get("blueprint_pools", []),
            "has_blueprints": bool(fi.get("blueprint_pools")),
        }

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Keyword search in faction name (case-insensitive)")
    parser.add_argument("--system", help="Filter to factions active in this system")
    parser.add_argument("--mission-type", help="Filter to factions offering this mission type")
    parser.add_argument("--has-blueprints", action="store_true", help="Only factions with blueprint rewards")
    parser.add_argument("--blueprint-type", help="Filter to factions whose pools contain this item type (e.g. quantumdrive)")
    parser.add_argument("--size", type=int, help="Blueprint size filter (e.g. 2)")
    parser.add_argument("--limit", type=int, default=10, help="Max results (default 10)")
    args = parser.parse_args()

    missions, merged, bp_data = load_data()
    index = build_faction_index(missions, merged, bp_data)

    results = list(index.values())

    # Apply filters
    if args.name:
        results = [f for f in results if args.name.lower() in f["name"].lower()]

    if args.system:
        results = [f for f in results if args.system in f["systems"]]

    if args.mission_type:
        results = [f for f in results if args.mission_type.lower() in
                   [mt.lower() for mt in f["mission_types"]]]

    if args.has_blueprints:
        results = [f for f in results if f["has_blueprints"]]

    if args.blueprint_type or args.size:
        def pool_matches(pool):
            if args.blueprint_type:
                if not any(args.blueprint_type.lower() in (t or "").lower()
                           for t in pool.get("blueprint_types", [])):
                    return False
            if args.size:
                target = f"size{args.size}"
                if bp_data:
                    for bp_entry in pool.get("blueprints", []):
                        # Handle both old format (string) and new format (dict)
                        entry_name = bp_entry.get("name") if isinstance(bp_entry, dict) else bp_entry
                        match = next(
                            (b for b in bp_data.get("blueprints", [])
                             if b.get("productName") == entry_name and b.get("subtype") == target),
                            None
                        )
                        if match:
                            return True
                    return False
            return True

        results = [f for f in results if any(pool_matches(p) for p in f.get("blueprint_pools", []))]

    # Sort: factions with blueprints first, then by mission count
    results.sort(key=lambda f: (-f["has_blueprints"], -f["mission_count"]))
    results = results[: args.limit]

    print(json.dumps({
        "query": {k: v for k, v in vars(args).items() if v},
        "count": len(results),
        "factions": results,
    }, indent=2))


if __name__ == "__main__":
    main()
