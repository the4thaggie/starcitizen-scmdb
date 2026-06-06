# Hermes-native maintenance notes

This skill was refactored to behave like a class-level Hermes skill rather than a narrow one-off.

## What to preserve
- Keep `SKILL.md` rich but compact: Overview, When to Use, routing rules, pitfall list, verification checklist.
- Put session-specific or maintenance detail in `references/` instead of flattening it into the main skill body.
- Keep the skill patch-aware, script-driven, and concise in user-facing answers.
- Preserve the one-question-at-a-time workflow for missing context.
- Keep source and local mirror copies synchronized when editing the repo version and the installed skill version.

## Useful script map
- `scripts/query/blueprint_unlock.py` — shortlist blueprint pools.
- `scripts/query/blueprint_materials.py` — material requirements.
- `scripts/query/mission_grind_plan.py` — reputation / grind planning.
- `scripts/query/mining_locations.py` — mining routes.
- `scripts/query/commodity_prices.py` — sell prices.
- `scripts/query/material_acquisition_plan.py` — full acquisition loop.
- `scripts/query/faction_search.py` — menu when the faction is unknown.
- `scripts/query/mining_solver.py` — laser / crackability / loadout questions.

## Maintenance reminder
If a user correction changes style, sequencing, or answer format for this skill class, encode it in `SKILL.md` rather than only in memory.