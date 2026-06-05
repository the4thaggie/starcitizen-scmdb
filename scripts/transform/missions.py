#!/usr/bin/env python3
"""
Transforms raw merged-<version>.json into a denormalized missions JSON
optimized for AI consumption. Resolves all ID references to human-readable
names and computes derived fields (est. UEC/h, est. rep/h).

Usage:
    python3 scripts/transform/missions.py <version>
    python3 scripts/transform/missions.py 4.8.1-live.11875683

Input:  data/raw/<version>/merged.json
Output: data/missions/<version>.json
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def load_raw(version: str) -> dict:
    path = REPO_ROOT / "data" / "raw" / version / "merged.json"
    if not path.exists():
        sys.exit(f"ERROR: {path} not found. Run scripts/fetch/scmdb_raw.py first.")
    with open(path) as f:
        return json.load(f)


def strip_markup(text: str) -> str:
    if not text:
        return text
    return re.sub(r"<[^>]+>", "", text).strip()


def resolve_location(pool_id: str, pools: dict) -> dict | None:
    loc = pools.get(pool_id)
    if not loc:
        return {"id": pool_id}
    return {
        "name": loc.get("name"),
        "type": loc.get("type"),
        "system": loc.get("system"),
        "planet": loc.get("planet"),
        "moon": loc.get("moon"),
    }


def transform_contract(contract: dict, raw: dict) -> dict:
    factions = raw["factions"]
    loc_pools = raw["locationPools"]
    faction_rewards_pools = raw["factionRewardsPools"]

    # Faction
    faction_guid = contract.get("factionGuid")
    faction_name = factions[faction_guid]["name"] if faction_guid and faction_guid in factions else None

    # Faction rep gains
    rep_index = contract.get("factionRewardsIndex")
    faction_rep_gains = []
    if rep_index is not None and rep_index < len(faction_rewards_pools):
        for gain in faction_rewards_pools[rep_index]:
            fg = gain.get("factionGuid")
            faction_rep_gains.append({
                "faction": factions[fg]["name"] if fg and fg in factions else fg,
                "amount": gain.get("amount"),
            })

    # Locations and destinations
    def resolve_all(ids):
        return [resolve_location(i, loc_pools) for i in (ids or [])]

    # Computed estimates
    time_min = contract.get("timeToComplete") or 0
    reward_uec = contract.get("rewardUEC") or 0
    est_uec_per_hour = round((reward_uec / time_min) * 60) if time_min > 0 else None

    total_rep = sum(g["amount"] for g in faction_rep_gains if g.get("amount"))
    est_rep_per_hour = round((total_rep / time_min) * 60) if time_min > 0 and total_rep > 0 else None

    # Standing
    def standing(s):
        if not s:
            return None
        return {"name": s.get("name"), "minReputation": s.get("minReputation")}

    # Prerequisites
    prereqs = contract.get("prerequisites") or {}
    prereq_locs = prereqs.get("location", [])

    # Ship encounters summary
    encounters = contract.get("shipEncounters")

    # Property values
    prop_vals = contract.get("propertyValues") or {}
    hauling_order_count = prop_vals.get("NumberOfHaulingOrders")

    # Chain detection
    is_chain = bool(contract.get("parentId") or contract.get("subContractIds"))

    return {
        "id": contract["id"],
        "title": contract.get("title"),
        "description": strip_markup(contract.get("description", "")),
        "faction": faction_name,
        "category": contract.get("category"),          # "career" | "story"
        "missionType": contract.get("missionType"),
        "systems": contract.get("systems", []),
        "illegal": contract.get("illegal", False),
        "canBeShared": contract.get("canBeShared", False),
        "rewardUEC": reward_uec,
        "timeToCompleteMinutes": time_min,
        "estUECPerHour": est_uec_per_hour,
        "factionRepGain": faction_rep_gains,
        "estRepPerHour": est_rep_per_hour,
        "minStanding": standing(contract.get("minStanding")),
        "maxStanding": standing(contract.get("maxStanding")),
        "prerequisites": prereq_locs,
        "locations": resolve_all(contract.get("locations")),
        "destinations": resolve_all(contract.get("destinations")),
        "onceOnly": contract.get("onceOnly", False),
        "maxPlayersPerInstance": contract.get("maxPlayersPerInstance"),
        "hasPersonalCooldown": contract.get("hasPersonalCooldown", False),
        "personalCooldownMinutes": contract.get("personalCooldownTime"),
        "isChain": is_chain,
        "parentId": contract.get("parentId"),
        "shipEncounters": encounters,
        "haulingOrderCount": hauling_order_count,
        "availableInPrison": contract.get("availableInPrison", False),
    }


def main():
    if len(sys.argv) < 2:
        # Auto-detect from data/VERSION
        version_file = REPO_ROOT / "data" / "VERSION"
        version = version_file.read_text().strip()
        if version == "UNINITIALIZED" or not version:
            sys.exit("ERROR: provide version argument or run fetch first.")
    else:
        version = sys.argv[1]

    print(f"=== Transform: missions ({version}) ===")

    raw = load_raw(version)

    contracts = raw.get("contracts", [])
    legacy = raw.get("legacyContracts", [])
    print(f"  Contracts:        {len(contracts)}")
    print(f"  Legacy contracts: {len(legacy)}")

    missions = [transform_contract(c, raw) for c in contracts]
    legacy_missions = [transform_contract(c, raw) for c in legacy]

    out = {
        "version": version,
        "count": len(missions),
        "legacyCount": len(legacy_missions),
        "missions": missions,
        "legacyMissions": legacy_missions,
    }

    out_path = REPO_ROOT / "data" / "missions" / f"{version}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    size_kb = out_path.stat().st_size // 1024
    print(f"  → {out_path.relative_to(REPO_ROOT)}  ({size_kb} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
