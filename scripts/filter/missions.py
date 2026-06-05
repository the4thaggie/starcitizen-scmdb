#!/usr/bin/env python3
"""
Filters and sorts the missions data file for AI consumption.
Reads data/missions/<version>.json, applies filters, outputs compact JSON.

Usage:
    python3 scripts/filter/missions.py [options]

Options:
    --faction <name>          Exact faction name match
    --system <name>           Mission available in this system
    --mission-type <type>     Mission type (Delivery, Bounty Hunter, Mercenary, ...)
    --min-reward <uec>        Minimum rewardUEC
    --max-standing <name>     Only missions accessible at or below this standing name
    --legal                   Exclude illegal missions
    --illegal                 Exclude legal missions (show only illegal)
    --no-combat               Exclude missions with ship encounters
    --repeatable              Exclude once-only missions
    --sort <field>            uec_per_hour | rep_per_hour | reward (default: uec_per_hour)
    --limit <n>               Max results (default: 20)
    --include-legacy          Also search legacy missions
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

STANDING_ORDER = [
    "Neutral",
    "Jr. Contractor",
    "Contractor",
    "Sr. Contractor",
    "Veteran",
    "Elite Contractor",
    "Ally",
    "Hostile",
]


def standing_rank(name: str | None) -> int:
    if name is None:
        return 0
    try:
        return STANDING_ORDER.index(name)
    except ValueError:
        return 0


def load_missions(version: str) -> tuple[list, list]:
    path = REPO_ROOT / "data" / "missions" / f"{version}.json"
    if not path.exists():
        sys.exit(f"ERROR: {path} not found. Run scripts/update_cache.sh first.")
    with open(path) as f:
        data = json.load(f)
    return data["missions"], data.get("legacyMissions", [])


def apply_filters(missions: list, args: argparse.Namespace) -> list:
    results = []
    for m in missions:
        if args.faction and m.get("faction") != args.faction:
            continue
        if args.system and args.system not in (m.get("systems") or []):
            continue
        if args.mission_type and m.get("missionType") != args.mission_type:
            continue
        if args.min_reward and (m.get("rewardUEC") or 0) < args.min_reward:
            continue
        if args.legal and m.get("illegal"):
            continue
        if args.illegal and not m.get("illegal"):
            continue
        if args.no_combat and m.get("shipEncounters"):
            continue
        if args.repeatable and m.get("onceOnly"):
            continue
        if args.max_standing:
            ms = m.get("minStanding")
            if ms and standing_rank(ms.get("name")) > standing_rank(args.max_standing):
                continue
        results.append(m)
    return results


def sort_key(m: dict, sort_field: str):
    if sort_field == "rep_per_hour":
        return -(m.get("estRepPerHour") or 0)
    if sort_field == "reward":
        return -(m.get("rewardUEC") or 0)
    return -(m.get("estUECPerHour") or 0)


def summarize(m: dict) -> dict:
    """Compact view for list output."""
    return {
        "id": m["id"],
        "title": m.get("title"),
        "faction": m.get("faction"),
        "missionType": m.get("missionType"),
        "systems": m.get("systems"),
        "rewardUEC": m.get("rewardUEC"),
        "estUECPerHour": m.get("estUECPerHour"),
        "estRepPerHour": m.get("estRepPerHour"),
        "minStanding": m.get("minStanding"),
        "illegal": m.get("illegal"),
        "combat": bool(m.get("shipEncounters")),
        "onceOnly": m.get("onceOnly"),
        "isChain": m.get("isChain"),
        "personalCooldownMinutes": m.get("personalCooldownMinutes"),
    }


def main():
    parser = argparse.ArgumentParser(description="Filter SCMDB missions data")
    parser.add_argument("--faction", default=None)
    parser.add_argument("--system", default=None)
    parser.add_argument("--mission-type", default=None)
    parser.add_argument("--min-reward", type=int, default=None)
    parser.add_argument("--max-standing", default=None)
    parser.add_argument("--legal", action="store_true")
    parser.add_argument("--illegal", action="store_true")
    parser.add_argument("--no-combat", action="store_true")
    parser.add_argument("--repeatable", action="store_true")
    parser.add_argument("--sort", default="uec_per_hour", choices=["uec_per_hour", "rep_per_hour", "reward"])
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--include-legacy", action="store_true")
    parser.add_argument("--full", action="store_true", help="Output full records, not summaries")
    args = parser.parse_args()

    version = (REPO_ROOT / "data" / "VERSION").read_text().strip()
    missions, legacy = load_missions(version)

    pool = missions
    if args.include_legacy:
        pool = missions + legacy

    filtered = apply_filters(pool, args)
    filtered.sort(key=lambda m: sort_key(m, args.sort))
    filtered = filtered[: args.limit]

    output = {
        "version": version,
        "filters_applied": {k: v for k, v in vars(args).items() if v and k not in ("full",)},
        "count": len(filtered),
        "missions": [m if args.full else summarize(m) for m in filtered],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
