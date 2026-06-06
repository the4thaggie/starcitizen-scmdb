#!/usr/bin/env python3
"""
Computes a rep grind plan for a faction from a given standing to a target tier.
The agent calls this after collecting: faction, current_rep, system, ship, party_size.

Usage:
    python3 scripts/query/mission_grind_plan.py \
        --faction "Covalex" \
        --current-rep 50 \
        --target-tier "Master" \
        --system Stanton \
        --ship Prospector \
        --party-size 1

Output (JSON):
    {
      "faction": "Covalex",
      "current_rep": 50,
      "current_tier": "Rookie",
      "target_tier": "Master",
      "target_rep": 237750,
      "ship": "Prospector",
      "ship_cargo_scu": 12,
      "party_size": 1,
      "tiers": [ { tier info + best mission + runs needed } ],
      "total_runs": 888,
      "total_est_hours": 89,
      "batching_notes": [...],
      "community_tips": [...]
    }
"""

import argparse
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

# Known ship cargo capacities (SCU). Add more as needed.
SHIP_CARGO = {
    "prospector": 12,
    "aurora mr": 6,
    "aurora cl": 6,
    "aurora es": 2,
    "aurora lx": 2,
    "reliant kore": 4,
    "cutlass black": 46,
    "freelancer": 66,
    "caterpillar": 576,
    "c2 hercules": 696,
    "constellation andromeda": 96,
    "mercury star runner": 114,
    "golem": 0,
    "mole": 96,
    "unknown": None,
}

# Mission type community notes
MISSION_TYPE_NOTES = {
    "Delivery": "Single pickup, single drop. Predictable, batchable if terminal overlaps.",
    "Recovery": "Pickup at fixed distress location shown on map. Fastest since no search needed.",
    "Hauling": "May involve multiple pickups or drops. Confirm total SCU before accepting.",
    "Escort": "Combat adjacent — protect a ship in transit. Not recommended for non-combat builds.",
    "Mercenary": "Combat required. Skip unless comfortable with PvP or NPC combat.",
    "Bounty Hunter": "Combat required. Ship encounters expected.",
    "Salvage": "Requires salvage-capable ship. Not applicable to Prospector/Aurora.",
}


def load_data():
    version = (REPO_ROOT / "data" / "VERSION").read_text().strip()
    path = REPO_ROOT / "data" / "missions" / f"{version}.json"
    if not path.exists():
        sys.exit(f"ERROR: {path} not found. Run scripts/update_cache.sh first.")
    with open(path) as f:
        return json.load(f)


def get_ship_scu(ship_name: str) -> int | None:
    return SHIP_CARGO.get(ship_name.lower().strip())


def find_faction_tiers(missions: list, faction: str) -> list[tuple[str, int]]:
    tiers = {}
    for m in missions:
        if m.get("faction") != faction:
            continue
        ms = m.get("minStanding")
        if not ms:
            continue
        name = ms.get("name")
        rep = ms.get("minReputation", 0)
        if name and name not in tiers:
            tiers[name] = rep
    return sorted(tiers.items(), key=lambda x: x[1])


def current_tier_name(current_rep: int, tiers: list[tuple[str, int]]) -> str:
    tier_name = tiers[0][0] if tiers else "Neutral"
    for name, min_rep in tiers:
        if current_rep >= min_rep:
            tier_name = name
    return tier_name


def best_mission_at_tier(missions: list, faction: str, tier_name: str, system: str | None,
                          party_size: int, ship_scu: int | None) -> dict | None:
    candidates = []
    for m in missions:
        if m.get("faction") != faction:
            continue
        if m.get("estRepPerHour") is None or m["estRepPerHour"] == 0:
            continue
        ms = m.get("minStanding") or {}
        if ms.get("name") != tier_name:
            continue
        if system and system not in (m.get("systems") or []):
            continue
        if m.get("shipEncounters") and party_size == 1:
            continue  # skip solo combat at default
        candidates.append(m)

    if not candidates:
        # Relax system filter
        for m in missions:
            if m.get("faction") != faction:
                continue
            if m.get("estRepPerHour") is None or m["estRepPerHour"] == 0:
                continue
            ms = m.get("minStanding") or {}
            if ms.get("name") != tier_name:
                continue
            candidates.append(m)

    if not candidates:
        return None

    best = max(candidates, key=lambda m: m.get("estRepPerHour", 0))
    mission_type = best.get("missionType", "")
    return {
        "id": best.get("id"),
        "title": best.get("title"),
        "debug_name": best.get("debugName"),
        "mission_type": mission_type,
        "systems": best.get("systems"),
        "rep_per_run": sum(g["amount"] for g in (best.get("factionRepGain") or []) if g.get("amount")),
        "uec_per_run": best.get("rewardUEC"),
        "time_minutes": best.get("timeToCompleteMinutes"),
        "rep_per_hour": best.get("estRepPerHour"),
        "uec_per_hour": best.get("estUECPerHour"),
        "combat": bool(best.get("shipEncounters")),
        "can_be_shared": best.get("canBeShared"),
        "cooldown_minutes": best.get("personalCooldownMinutes"),
        "type_note": MISSION_TYPE_NOTES.get(mission_type, ""),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--faction", required=True)
    parser.add_argument("--current-rep", type=int, default=0)
    parser.add_argument("--target-tier", default=None, help="Target tier name (default: highest)")
    parser.add_argument("--system", default=None, help="Stanton | Pyro | Nyx")
    parser.add_argument("--ship", default="unknown")
    parser.add_argument("--party-size", type=int, default=1)
    args = parser.parse_args()

    data = load_data()
    missions = data["missions"]

    ship_scu = get_ship_scu(args.ship)
    tiers = find_faction_tiers(missions, args.faction)

    if not tiers:
        print(json.dumps({"error": f"No missions found for faction: {args.faction}"}))
        return

    all_tier_names = [t[0] for t in tiers]
    target_tier = args.target_tier or tiers[-1][0]
    if target_tier not in all_tier_names:
        print(json.dumps({"error": f"Unknown tier '{target_tier}' for {args.faction}. Valid: {all_tier_names}"}))
        return

    target_rep = dict(tiers)[target_tier]
    cur_tier = current_tier_name(args.current_rep, tiers)

    # Build tier-by-tier plan from current position to target
    plan_tiers = []
    total_runs = 0
    total_minutes = 0.0

    current_idx = next((i for i, (n, _) in enumerate(tiers) if n == cur_tier), 0)
    target_idx = next((i for i, (n, _) in enumerate(tiers) if n == target_tier), len(tiers) - 1)

    for i in range(current_idx, target_idx):
        from_tier_name, from_rep = tiers[i]
        to_tier_name, to_rep = tiers[i + 1]

        start_rep = max(args.current_rep, from_rep) if i == current_idx else from_rep
        rep_needed = to_rep - start_rep
        if rep_needed <= 0:
            continue

        best = best_mission_at_tier(missions, args.faction, from_tier_name,
                                     args.system, args.party_size, ship_scu)
        if not best or best["rep_per_run"] == 0:
            plan_tiers.append({
                "from_tier": from_tier_name,
                "to_tier": to_tier_name,
                "rep_needed": rep_needed,
                "best_mission": None,
                "runs_needed": None,
                "note": "No rep-granting missions found at this tier in specified system.",
            })
            continue

        runs = math.ceil(rep_needed / best["rep_per_run"])
        est_minutes = runs * (best["time_minutes"] or 20)
        total_runs += runs
        total_minutes += est_minutes

        plan_tiers.append({
            "from_tier": from_tier_name,
            "to_tier": to_tier_name,
            "rep_needed": rep_needed,
            "best_mission": best,
            "runs_needed": runs,
            "est_hours": round(est_minutes / 60, 1),
        })

    # Batching and community notes
    batching_notes = []
    if ship_scu is not None and ship_scu < 20:
        batching_notes.append(
            f"{args.ship} has ~{ship_scu} SCU cargo. Most single Delivery/Recovery missions fit. "
            "Bulk hauls at Senior+ may exceed capacity — check mission SCU before accepting."
        )
    if args.party_size > 1:
        batching_notes.append(
            f"With {args.party_size} players: shared missions split the rep among all party members "
            "unless mission is non-shareable. Verify canBeShared before grouping."
        )
    batching_notes.append(
        "Covalex Direct Delivery missions share the same terminal — you can accept multiple "
        "back-to-back with the same route, maximizing time between terminal visits."
    )

    community_tips = [
        "Recovery missions show the pickup waypoint on your map — no searching required. "
        "Fastest rep/hour for most tiers.",
        "Bookmark the Covalex terminal location to reduce spawn travel between missions.",
        "Cooldown timers run in real-time. Queue multiple mission types (Recovery + Delivery) "
        "to alternate while timers reset.",
    ]
    if args.party_size == 1:
        community_tips.append("Solo: avoid missions with ship encounters unless you have a combat-capable loadout.")

    result = {
        "faction": args.faction,
        "current_rep": args.current_rep,
        "current_tier": cur_tier,
        "target_tier": target_tier,
        "target_rep": target_rep,
        "ship": args.ship,
        "ship_cargo_scu": ship_scu,
        "party_size": args.party_size,
        "system": args.system or "any",
        "tiers": plan_tiers,
        "total_runs": total_runs,
        "total_est_hours": round(total_minutes / 60, 1),
        "batching_notes": batching_notes,
        "community_tips": community_tips,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
