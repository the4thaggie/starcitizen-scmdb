# Mining Solver Subskill — Entry Point

## When to use this subskill
Loaded by SKILL.md when the user asks about mining ship configuration, laser/module selection, rock parameters, or computed mining stats.

If the user needs math performed, also load `instructions/mining_solver/math.md`.
When formatting a final recommendation, also load `instructions/mining_solver/output_formats.md`.

## Data files
- `data/mining/equipment.json` — all lasers, modules, ships and their base stats (patch-stable)
- `data/mining/<version>.json` — any solver constants that change per patch
- `schemas/mining.schema.json` — field definitions

## Mining archetypes
Three distinct archetypes with different equipment trees:
- **Ship Mining** — Prospector (1 laser), Golem (1 laser), Mole (1–3 lasers)
- **ROC/Geo** — vehicle-mounted ground mining
- **Hand Mining** — multi-tool with mining attachment

Always confirm the archetype before proceeding.

## Ship mining configuration flow
1. Confirm ship selection (Prospector / Golem / Mole)
2. For Mole: confirm number of active laser operators (1, 2, or 3)
3. For each laser hardpoint: select mining head from `equipment.json`
   - Note head-specific module slot count (Arbor: 1, Klein: 0, Helix: 2, etc.)
4. For each module slot: select passive or active module
   - Passive: persistent stat modifier while installed
   - Active: limited charges, consumed on use
5. Confirm gadget preference (default: no gadgets unless user requests)
6. Read resulting Stats panel from `data/mining/<version>.json` formulas

## Equipment lookup
<!-- TODO: expand after equipment.json schema is finalized with full laser/module catalog -->

## Known gotchas
<!-- TODO: populate after first scrape and calibration run -->
