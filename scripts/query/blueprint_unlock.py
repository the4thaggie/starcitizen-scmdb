#!/usr/bin/env python3
"""
Returns the faction, standing tier, and blueprint pool for a blueprint.
The agent should identify the blueprint with blueprint_lookup.py first, then pass the exact guid or name here.

Usage:
    python3 scripts/query/blueprint_lookup.py --name "Yeager"
    python3 scripts/query/blueprint_unlock.py --guid "<guid>"
    python3 scripts/query/blueprint_unlock.py --name "Yeager"
    python3 scripts/query/blueprint_unlock.py --search "quantum drive" --size 2 --type military

Output (JSON):
    {
      "found": true,
      "name": "Yeager",
      "manufacturer": "Wei-Tek",
      "type": "quantumdrive",
      "subtype": "size2",
      "craft_time_seconds": 1230,
      "faction": "Covalex",
      "min_tier": "Master",
      "min_rep": 237750,
      "pool_name": "BP_REWARDS_CovalexSuper",
      "pool_size": 9,
      "pool_blueprints": [...],
      "expected_runs_for_this_bp": 9,
      "alternatives": [...]        // other blueprints in the same pool
    }
"""

import argparse
import json
import sys
from pathlib import Path

from blueprint_lookup import exact_lookup

REPO_ROOT = Path(__file__).parent.parent.parent


def load_data():
    version = (REPO_ROOT / "data" / "VERSION").read_text().strip()
    bp_path = REPO_ROOT / "data" / "raw" / version / "crafting_blueprints.json"
    merged_path = REPO_ROOT / "data" / "raw" / version / "merged.json"
    if not bp_path.exists() or not merged_path.exists():
        sys.exit("ERROR: Run scripts/update_cache.sh first.")
    with open(bp_path) as f:
        bp_data = json.load(f)
    with open(merged_path) as f:
        merged = json.load(f)
    return bp_data, merged


def load_wiki_index() -> dict:
    index = {}
    for fname in ("quantum_drives.json", "mining_lasers.json"):
        path = REPO_ROOT / "data" / "wiki" / fname
        if path.exists():
            with open(path) as f:
                index.update(json.load(f))
    return index


def normalize(value: str | None) -> str:
    return (value or "").strip().casefold()


def search_blueprints(bp_data, name=None, search=None, size=None, bp_type=None):
    bps = bp_data["blueprints"]
    results = []
    for b in bps:
        prod = normalize(b.get("productName"))
        tag = normalize(b.get("tag"))
        if name and normalize(name) != prod and normalize(name) != tag:
            continue
        if search:
            terms = [normalize(kw) for kw in search.split() if kw.strip()]
            if not all(term == prod or term == tag or term in prod or term in tag for term in terms):
                continue
        if size and b.get("subtype") != f"size{size}":
            continue
        if bp_type and normalize(bp_type) != normalize(b.get("type")):
            continue
        results.append(b)
    return results


def get_faction_unlock(bp_guid, merged):
    factions = merged["factions"]
    bp_pools = merged["blueprintPools"]
    contracts = merged["contracts"]
    faction_rewards_pools = merged["factionRewardsPools"]

    # Find blueprint pool containing this guid
    containing_pool_id = None
    containing_pool = None
    for pool_id, pool in bp_pools.items():
        for entry in pool.get("blueprints", []):
            if entry.get("blueprintRecord") == bp_guid:
                containing_pool_id = pool_id
                containing_pool = pool
                break
        if containing_pool:
            break

    if not containing_pool:
        return None, None, None

    # Find contracts that reference this pool
    pool_id_str = containing_pool_id
    matching_contracts = [c for c in contracts if pool_id_str in json.dumps(c)]

    if not matching_contracts:
        return containing_pool, None, None

    # Find the contract with the highest minStanding (the unlock tier)
    def rep_key(c):
        ms = c.get("minStanding") or {}
        return ms.get("minReputation", 0)

    representative = max(matching_contracts, key=rep_key)
    faction_guid = representative.get("factionGuid")
    faction_name = factions[faction_guid]["name"] if faction_guid and faction_guid in factions else None
    return containing_pool, faction_name, representative


def tier_path(faction_name, merged):
    """Return all rep tiers for this faction, sorted ascending."""
    factions = merged["factions"]
    contracts = merged["contracts"]
    faction_guid = next((g for g, f in factions.items() if f.get("name") == faction_name), None)
    if not faction_guid:
        return []
    tiers = {}
    for c in contracts:
        if c.get("factionGuid") != faction_guid:
            continue
        ms = c.get("minStanding") or {}
        name = ms.get("name")
        rep = ms.get("minReputation", 0)
        if name and name not in tiers:
            tiers[name] = rep
    return sorted(tiers.items(), key=lambda x: x[1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Exact blueprint product name")
    parser.add_argument("--guid", help="Exact blueprint GUID")
    parser.add_argument("--search", help="Keyword search across name and tag (legacy/manual only)")
    parser.add_argument("--size", type=int, help="Size filter (e.g. 2)")
    parser.add_argument("--type", dest="bp_type", help="Type filter (e.g. quantumdrive)")
    args = parser.parse_args()

    if not args.name and not args.search and not args.guid:
        sys.exit("ERROR: provide --guid, --name, or --search")

    bp_data, merged = load_data()
    factions = merged["factions"]
    wiki = load_wiki_index()

    if args.guid or args.name:
        matches = exact_lookup(bp_data, guid=args.guid, name=args.name)
    else:
        matches = search_blueprints(bp_data, name=None, search=args.search,
                                     size=args.size, bp_type=args.bp_type)
        if args.size or args.bp_type:
            # search_blueprints already applied the filters above, but keep the branch explicit.
            pass

    if not matches:
        print(json.dumps({"found": False, "query": vars(args)}))
        return

    if len(matches) > 1 and args.name and not args.guid:
        # Exact names can still map to multiple records; keep all exact matches.
        matches = [b for b in matches if normalize(b.get("productName")) == normalize(args.name)
                   or normalize(b.get("tag")) == normalize(args.name)]

    if len(matches) > 5:
        # Too many — return summary list for agent to narrow
        summary = [{"guid": b.get("guid"), "name": b.get("productName") or b.get("tag"), "type": b.get("type"),
                    "subtype": b.get("subtype"), "manufacturer": b.get("manufacturer")} for b in matches[:20]]
        print(json.dumps({"found": "multiple", "count": len(matches), "results": summary,
                          "hint": "Refine search with --size, --type, or more specific --name"}))
        return

    results = []
    for b in matches:
        pool, faction_name, rep_contract = get_faction_unlock(b["guid"], merged)

        pool_blueprints = []
        pool_name = None
        pool_size = 0
        if pool:
            pool_name = pool.get("name")
            pool_blueprints = [e.get("name") for e in pool.get("blueprints", [])]
            pool_size = len(pool_blueprints)

        min_tier = None
        min_rep = None
        if rep_contract:
            ms = rep_contract.get("minStanding") or {}
            min_tier = ms.get("name")
            min_rep = ms.get("minReputation")
            faction_guid = rep_contract.get("factionGuid")
            if not faction_name and faction_guid:
                faction_name = factions.get(faction_guid, {}).get("name")

        tiers = tier_path(faction_name, merged) if faction_name else []
        bp_name = b.get("productName") or b.get("tag")
        wiki_entry = wiki.get(bp_name, {})

        result = {
            "found": True,
            "guid": b.get("guid"),
            "name": bp_name,
            "manufacturer": b.get("manufacturer"),
            "type": b.get("type"),
            "subtype": b.get("subtype"),
            "grade": wiki_entry.get("grade"),    # A/B/C/D quality tier (from SC Wiki)
            "class": wiki_entry.get("class"),    # Military/Civilian/Industrial/Stealth
            "craft_time_seconds": b["tiers"][0]["craftTimeSeconds"] if b.get("tiers") else None,
            "faction": faction_name,
            "min_tier": min_tier,
            "min_rep": min_rep,
            "pool_name": pool_name,
            "pool_size": pool_size,
            "pool_blueprints": pool_blueprints,
            "expected_runs_for_this_bp": pool_size,
            "faction_tiers": [{"tier": t, "min_rep": r} for t, r in tiers],
        }
        results.append(result)

    if len(results) == 1:
        print(json.dumps(results[0], indent=2))
    else:
        print(json.dumps({"found": "multiple", "count": len(results), "results": results}, indent=2))


if __name__ == "__main__":
    main()
