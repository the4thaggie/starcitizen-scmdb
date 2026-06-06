#!/usr/bin/env python3
"""Exact mission lookup from authoritative SCMDB JSON.

This script intentionally avoids web search and page-snippet guessing.
Use it to resolve a mission by exact id, debug name, or title from the
local SCMDB data set for the current patch.

Examples:
    python3 scripts/query/mission_lookup.py --id 12a94de8-d1a1-489b-a866-2bc745b02413
    python3 scripts/query/mission_lookup.py --debug-name Covalex_Nyx_Hard_RecoverCargo
    python3 scripts/query/mission_lookup.py --title "Large Covalex Shipment Needs Recovering"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def load_data() -> tuple[str, list[dict]]:
    version = (REPO_ROOT / "data" / "VERSION").read_text().strip()
    path = REPO_ROOT / "data" / "raw" / version / "merged.json"
    if not path.exists():
        sys.exit(f"ERROR: {path} not found. Run scripts/update_cache.sh first.")
    with open(path) as f:
        merged = json.load(f)
    return version, merged.get("contracts", [])


def normalize(value: str | None) -> str:
    return (value or "").strip().casefold()


def mission_record(contract: dict) -> dict:
    ms = contract.get("minStanding") or {}
    mx = contract.get("maxStanding") or {}
    rep_gains = contract.get("factionRepGain") or []
    return {
        "id": contract.get("id"),
        "title": contract.get("title"),
        "debug_name": contract.get("debugName"),
        "faction": contract.get("faction"),
        "category": contract.get("category"),
        "mission_type": contract.get("missionType"),
        "systems": contract.get("systems") or [],
        "reward_uec": contract.get("rewardUEC"),
        "time_to_complete_minutes": contract.get("timeToComplete"),
        "can_be_shared": contract.get("canBeShared"),
        "illegal": contract.get("illegal"),
        "ship_encounters": bool(contract.get("shipEncounters")),
        "min_standing": {
            "name": ms.get("name"),
            "min_reputation": ms.get("minReputation"),
        } if ms else None,
        "max_standing": {
            "name": mx.get("name"),
            "min_reputation": mx.get("minReputation"),
        } if mx else None,
        "faction_rep_gain": [
            {"faction": g.get("faction"), "amount": g.get("amount")}
            for g in rep_gains
            if g
        ],
        "prerequisites": contract.get("prerequisites"),
        "locations": contract.get("locations") or [],
        "destinations": contract.get("destinations") or [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Exact mission lookup from SCMDB JSON")
    parser.add_argument("--id", dest="mission_id", help="Exact mission UUID")
    parser.add_argument("--debug-name", help="Exact debugName value")
    parser.add_argument("--title", help="Exact mission title")
    parser.add_argument("--faction", help="Optional faction filter")
    parser.add_argument("--system", help="Optional system filter")
    args = parser.parse_args()

    if not (args.mission_id or args.debug_name or args.title):
        sys.exit("ERROR: provide --id, --debug-name, or --title")

    version, contracts = load_data()

    matches = []
    for c in contracts:
        if args.faction and c.get("faction") != args.faction:
            continue
        if args.system and args.system not in (c.get("systems") or []):
            continue
        if args.mission_id and c.get("id") != args.mission_id:
            continue
        if args.debug_name and normalize(c.get("debugName")) != normalize(args.debug_name):
            continue
        if args.title and normalize(c.get("title")) != normalize(args.title):
            continue
        matches.append(c)

    if not matches:
        print(json.dumps({
            "found": False,
            "version": version,
            "query": {
                "id": args.mission_id,
                "debug_name": args.debug_name,
                "title": args.title,
                "faction": args.faction,
                "system": args.system,
            },
        }, indent=2))
        return

    results = [mission_record(c) for c in matches]
    if len(results) == 1:
        print(json.dumps({"found": True, "version": version, **results[0]}, indent=2))
    else:
        print(json.dumps({
            "found": "multiple",
            "version": version,
            "count": len(results),
            "results": results,
        }, indent=2))


if __name__ == "__main__":
    main()
