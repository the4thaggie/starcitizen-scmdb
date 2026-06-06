# Deterministic lookup patterns

Use this reference when answering SCMDB questions that depend on record identity, especially missions, blueprints, mining equipment, and related discovery helpers.

## Core rule
- Prefer exact lookup from local SCMDB data first.
- Use stable identifiers when available:
  - mission `id`
  - blueprint `guid`
- Do not infer identity from title snippets, search ranking, or partial-name matches when the local dataset already contains the record.
- Discovery helpers may return candidate menus, but the main answer path should stay exact-first and deterministic.
- If a helper returns candidates, do not silently pick the first one; ask for the exact identifier or present the candidates explicitly.

## Mission identity
- Use `scripts/query/mission_lookup.py` for exact mission resolution.
- Exact record fields to surface when needed:
  - `id`
  - `title`
  - `systems`
  - `debug_name`
- Do not attach a page URL unless the exact record-to-URL mapping has been verified.
- Duplicate mission titles across Stanton / Nyx / Pyro are normal.

## Blueprint identity
- Use `scripts/query/blueprint_lookup.py` first.
- Pass the resulting `guid` into unlock / material / acquisition scripts.
- If the user only gives a vague item name, present explicit candidates or ask for the exact blueprint, rather than silently narrowing by substring.
- `blueprint_unlock.py` now accepts `--guid` and should be preferred over any title-only path.

## Mining solver identity
- Treat `--laser`, `--modules`, and `--rock-material` as exact names in the main flow.
- If the name is not exact, return candidate hints or direct the user to `--list-equipment`.
- Exact inputs reduce false positives because mining equipment names often share prefixes.
- `mining_solver.py` now fails closed on partial names instead of guessing.

## Faction search identity
- Prefer exact faction names with `--name <exact>`.
- If the faction is only partially remembered, return `found: false` plus `candidates` rather than guessing from a keyword fragment.

## Material / terminal identity
- Mining material names should be exact canonical names from the data.
- Refinery terminal names should be compared exactly, case-insensitive.
- If a target cannot be resolved, return the exact missing token plus candidate names.

## Session-verified helper examples
```bash
python3 scripts/query/mission_lookup.py --title 'Large Covalex Shipment Needs Recovering'
python3 scripts/query/blueprint_lookup.py --guid 07390e16-f481-4039-aeb8-a68c74cda400
python3 scripts/query/mining_solver.py --laser 'Arbor MH1 Mining Laser' --modules 'Focus II Module' --rock-material 'Ouratite' --ship prospector
python3 scripts/query/mining_solver.py --laser 'Arbor' --rock-material 'Ouratite' --ship prospector
python3 scripts/query/faction_search.py --name Covalex
python3 scripts/query/faction_search.py --name Cov
```

## Common pitfall
- Discovery helpers may still support loose matching for menu generation, but the main answer path should stay exact-first and deterministic.
