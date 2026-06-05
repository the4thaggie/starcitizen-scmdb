# starcitizen-scmdb — Design Document

An AI agent skill that answers Star Citizen gameplay questions about **missions, crafting blueprints, and mining** using patch-versioned data from SCMDB.net, enriched with live commodity prices from UEX Corp and base item stats from the SC Wiki.

**No authentication or API key is required.** All data sources used are public.

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Repository Layout](#3-repository-layout)
4. [Data Sources](#4-data-sources)
   - [4.1 SCMDB.net](#41-scmdbnet)
   - [4.2 UEX Corp API](#42-uex-corp-api)
   - [4.3 SC Wiki API](#43-sc-wiki-api)
5. [Data Pipeline](#5-data-pipeline)
6. [Skill Entry Point](#6-skill-entry-point)
   - [6.1 Intent Routing](#61-intent-routing)
   - [6.2 Output Rules](#62-output-rules)
7. [Subskill: Fabricator](#7-subskill-fabricator)
8. [Subskill: Missions](#8-subskill-missions)
9. [Subskill: Resources](#9-subskill-resources)
10. [Subskill: Mining Solver](#10-subskill-mining-solver)
11. [Query Script Reference](#11-query-script-reference)
    - [faction_search.py](#faction-search)
    - [mission_grind_plan.py](#mission-grind-plan)
    - [blueprint_unlock.py](#blueprint-unlock)
    - [blueprint_materials.py](#blueprint-materials)
    - [mining_locations.py](#mining-locations)
    - [mining_solver.py](#mining-solver-script)
    - [commodity_prices.py](#commodity-prices)
    - [material_acquisition_plan.py](#material-acquisition-plan)
12. [Transform Script Reference](#12-transform-script-reference)
    - [missions.py](#transform-missions)
    - [fabricator.py](#transform-fabricator)
    - [resources.py](#transform-resources)
    - [mining_equipment.py](#transform-mining-equipment)
    - [wiki_items.py](#transform-wiki-items)
13. [Ships Modeled](#13-ships-modeled)
14. [Patch Freshness](#14-patch-freshness)
15. [Future Features](#15-future-features)
16. [Subskill: Vision — HUD Screenshot Parsing](#16-subskill-vision--hud-screenshot-parsing)

---

## 1. Purpose

This repo builds and maintains a **Claude AI skill** for [SCMDB.net](https://scmdb.net) — a Star Citizen community database. The skill answers in-game questions about missions, crafting blueprints, and mining by running small Python query scripts against patch-versioned cached data rather than loading large JSON files into context.

Token cost to the end user is minimised by:
- Caching SCMDB data at patch time (not fetched on every query)
- Never loading a full data file into context — always delegating to a `scripts/query/` script
- Fetching live UEX prices only when the user explicitly asks for sell prices or an acquisition plan

[↑ Contents](#table-of-contents)

---

## 2. High-Level Architecture

```
User request
     │
     ▼
SKILL.md  ── top-level decision tree (intent routing)
     │
     ├── instructions/fabricator.md       Blueprint + grind + materials full flow
     ├── instructions/missions.md         Rep grinding and rank path planning
     ├── instructions/resources.md        Mining locations, route, acquisition plan
     └── instructions/mining_solver/      Loadout config, crack math, recommendations
              index.md  math.md  output_formats.md
                    │
                    ▼
          scripts/query/  ── one script per answer type, always JSON output
                    │
                    ▼
          data/  ── cached patch-versioned files + live UEX lookups at runtime
```

The agent **never loads full data files into context.** It always delegates to a `scripts/query/` script and reads the returned JSON.

[↑ Contents](#table-of-contents)

---

## 3. Repository Layout

```
starcitizen-scmdb/
├── SKILL.md                         Entry point loaded by agent runtime
├── DesignDoc.md                     This document
├── .env.example                     Documents optional future token (not currently used)
│
├── instructions/
│   ├── fabricator.md                Subskill: blueprint lookup, materials, dismantle
│   ├── missions.md                  Subskill: faction grind planning
│   ├── resources.md                 Subskill: mining locations, route, acquisition plan
│   ├── vision.md                    Subskill: screenshot intake, HUD parsing, result routing
│   └── mining_solver/
│       ├── index.md                 Subskill entry: loadout collection, modes
│       ├── math.md                  Reference: modifier math and game mechanics
│       └── output_formats.md        Reference: exact table and badge layouts
│
├── schemas/
│   ├── missions.schema.json
│   ├── fabricator.schema.json
│   ├── resources.schema.json
│   ├── mining.schema.json
│   └── vision.schema.json           HUD parse output (reputation result + error result)
│
├── scripts/
│   ├── update_cache.sh              Full pipeline runner — run after each game patch
│   │
│   ├── fetch/
│   │   ├── scmdb_raw.py             Downloads raw SCMDB JSON for current patch
│   │   ├── uex_api.py               Fetches static UEX reference data
│   │   └── wiki_api.py              Fetches item + ship stats from SC Wiki
│   │
│   ├── transform/
│   │   ├── missions.py              Raw merged.json → AI-ready missions JSON
│   │   ├── fabricator.py            crafting_blueprints.json → AI-ready fabricator JSON
│   │   ├── resources.py             mining_data.json → location + material dual-index
│   │   ├── mining_equipment.py      mining_equipment.json → normalized equipment.json
│   │   └── wiki_items.py            Wiki raw JSON → compact indexed files
│   │
│   ├── query/
│   │   ├── faction_search.py        Faction browser (by system, type, blueprint reward)
│   │   ├── mission_grind_plan.py    Rep grind plan from current standing to target tier
│   │   ├── blueprint_unlock.py      Faction + pool + standing requirement for a blueprint
│   │   ├── blueprint_materials.py   Material slots, quantities, quality→stat tables
│   │   ├── mining_locations.py      Best locations for target materials with crack hints
│   │   ├── mining_solver.py         Net stats for a laser+module loadout vs a rock
│   │   ├── commodity_prices.py      Live UEX sell prices for raw + refined materials
│   │   └── material_acquisition_plan.py  Ore budget, trips, refinery ranking, economics
│   │
│   └── vision/
│       ├── hud_parse.py             CLI: --hud <type> --image <path> → JSON
│       ├── hud_layouts.json         Crop region definitions (fractional coords, 16:9)
│       ├── calibrate.py             Visual helper: overlay regions on a reference screenshot
│       └── parsers/
│           ├── _base.py             Shared: image load, crop, OCR, bar fill measurement
│           └── reputation.py        MobiGlas Reputation tab → faction + rank + progress
│
└── data/
    ├── VERSION                      Current patch (e.g. 4.8.1-live.11875683)
    ├── raw/<version>/               SCMDB raw downloads — gitignored
    │   ├── merged.json
    │   ├── crafting_blueprints.json
    │   ├── crafting_items.json
    │   ├── mission_history.json
    │   ├── mining_data.json
    │   └── mining_equipment.json
    │
    ├── missions/<version>.json      Transformed, denormalized missions (committed)
    ├── fabricator/<version>.json    Transformed blueprints with unlock + quality tables
    ├── resources/<version>.json     Location index + material index (dual-indexed)
    ├── mining/equipment.json        Normalized equipment (version-tracked internally)
    │
    ├── uex/                         Static UEX Corp reference data (committed)
    │   ├── commodities.json
    │   ├── refinery_terminals.json
    │   ├── refinery_terminal_ids.json
    │   ├── refinery_methods.json
    │   └── refinery_yields.json
    │
    └── wiki/                        SC Wiki data (committed)
        ├── raw/                     Raw API responses — gitignored
        ├── quantum_drives.json      Transformed: name-keyed, base-variant-only
        ├── mining_lasers.json       Transformed: name-keyed, base-variant-only
        └── ships.json               Transformed: slug-keyed ship stats
```

**Key files:**

| File | Purpose |
|---|---|
| [`SKILL.md`](SKILL.md) | Agent entry point — intent routing and output rules |
| [`instructions/fabricator.md`](instructions/fabricator.md) | Blueprint + grind + mining full flow |
| [`instructions/missions.md`](instructions/missions.md) | Faction rep grinding workflow |
| [`instructions/resources.md`](instructions/resources.md) | Mining locations and acquisition plan |
| [`instructions/mining_solver/index.md`](instructions/mining_solver/index.md) | Loadout config and crackability |
| [`instructions/vision.md`](instructions/vision.md) | Screenshot intake and HUD parsing |
| [`scripts/vision/hud_parse.py`](scripts/vision/hud_parse.py) | HUD screenshot → JSON (CLI entry point) |
| [`scripts/vision/hud_layouts.json`](scripts/vision/hud_layouts.json) | Crop region coordinates for each HUD type |
| [`scripts/update_cache.sh`](scripts/update_cache.sh) | Full pipeline runner |

[↑ Contents](#table-of-contents)

---

## 4. Data Sources

### 4.1 SCMDB.net

Base URL: `https://scmdb.net/data` — static per patch, no authentication.

Fetched by [`scripts/fetch/scmdb_raw.py`](scripts/fetch/scmdb_raw.py).

| File pattern | Contents |
|---|---|
| `game-versions.json` | Available patches; first entry = current |
| `merged-<version>.json` | Factions, contracts, location pools, blueprint pools, faction reward pools |
| `crafting_blueprints-<version>.json` | Blueprints: GUID, slots, material options, modifier curves, dismantle config |
| `crafting_items-<version>.json` | Craftable item registry |
| `mission-history-<version>.json` | Historical mission completion data |
| `mining_data-<version>.json` | Locations, compositions, mineable elements (instability/resistance/quality bands) |
| `mining_equipment-<version>.json` | Lasers, modules, gadgets, globalParams physics constants |

All raw files are written to `data/raw/<version>/` (gitignored). Current patch stored in `data/VERSION`.

### 4.2 UEX Corp API

Base URL: `https://api.uexcorp.uk/2.0` — all endpoints public, no authentication.

| Endpoint | Fetch cadence | Destination |
|---|---|---|
| `commodities` | Cache (run `uex_api.py`) | `data/uex/commodities.json` |
| `terminals?type=commodity&is_refinery=1` | Cache | `data/uex/refinery_terminals.json` |
| `terminals?type=refinery` | Cache | `data/uex/refinery_terminal_ids.json` |
| `refineries_methods` | Cache | `data/uex/refinery_methods.json` |
| `refineries_yields` | Cache | `data/uex/refinery_yields.json` |
| `commodities_prices` | **Live at query time** | Not cached — fetched by [`commodity_prices.py`](scripts/query/commodity_prices.py) |
| `terminals_distances` | **Live at query time** | Not cached — fetched by [`material_acquisition_plan.py`](scripts/query/material_acquisition_plan.py) |

Commodity prices update approximately every 30 minutes (community-reported).

Static reference data is fetched by [`scripts/fetch/uex_api.py`](scripts/fetch/uex_api.py).

### 4.3 SC Wiki API

Base URL: `https://api.star-citizen.wiki/api/v2` — public, paginated at 100 items per page.

Fetched by [`scripts/fetch/wiki_api.py`](scripts/fetch/wiki_api.py).

| Endpoint | Contents | Destination |
|---|---|---|
| `items?filter[type]=QuantumDrive` | Drive speed, cooldown, spool, fuel efficiency | `data/wiki/raw/quantum_drives.json` |
| `items?filter[type]=WeaponMining` | Laser power range, module slots, modifier map | `data/wiki/raw/mining_lasers.json` |
| `vehicles?filter[name]=<ship>` | Cargo, speed, QD speed, fuel | `data/wiki/raw/ships.json` |

The transform step ([`wiki_items.py`](scripts/transform/wiki_items.py)) filters to base variants only (skips collector editions and skins) and writes name-keyed output to `data/wiki/`.

[↑ Contents](#table-of-contents)

---

## 5. Data Pipeline

Run [`scripts/update_cache.sh`](scripts/update_cache.sh) after each game patch.

| Step | Script | Input | Output |
|---|---|---|---|
| 1 | [`fetch/scmdb_raw.py`](scripts/fetch/scmdb_raw.py) | `scmdb.net/data` | `data/raw/<version>/` + `data/VERSION` |
| 2 | [`transform/missions.py`](scripts/transform/missions.py) | `raw/<v>/merged.json` | `data/missions/<version>.json` |
| 3 | [`transform/fabricator.py`](scripts/transform/fabricator.py) | `raw/<v>/crafting_blueprints.json` + `merged.json` | `data/fabricator/<version>.json` |
| 4 | [`transform/resources.py`](scripts/transform/resources.py) | `raw/<v>/mining_data.json` | `data/resources/<version>.json` |
| 5 | [`fetch/uex_api.py`](scripts/fetch/uex_api.py) | `api.uexcorp.uk` | `data/uex/*.json` |
| 6 | [`fetch/wiki_api.py`](scripts/fetch/wiki_api.py) | `api.star-citizen.wiki` | `data/wiki/raw/*.json` |
| 6b | [`transform/wiki_items.py`](scripts/transform/wiki_items.py) | `data/wiki/raw/*.json` | `data/wiki/*.json` |
| 7 | [`transform/mining_equipment.py`](scripts/transform/mining_equipment.py) | `raw/<v>/mining_equipment.json` | `data/mining/equipment.json` |

After running, commit `data/VERSION` and the transformed files. Raw downloads in `data/raw/` are gitignored.

[↑ Contents](#table-of-contents)

---

## 6. Skill Entry Point

Defined in [`SKILL.md`](SKILL.md).

The agent reads `data/VERSION` before any query and cites the patch in every answer.

### 6.1 Intent Routing

| Branch | Trigger keywords | Delegates to |
|---|---|---|
| Blueprint + Grind + Materials | blueprint, item to craft, rep grinding for a reward | [`instructions/fabricator.md`](instructions/fabricator.md) |
| Missions only | missions, reputation, rank grinding, "what missions should I run" | [`instructions/missions.md`](instructions/missions.md) |
| Resources / Mining locations | where to mine, best mining locations, ore concentrations, sell prices | [`instructions/resources.md`](instructions/resources.md) |
| Mining solver / loadout | laser selection, module config, rock crackability, mining stats | [`instructions/mining_solver/index.md`](instructions/mining_solver/index.md) |

### 6.2 Output Rules

- Always lead with patch version: `[Data: patch 4.8.1-live.11875683]`
- Never reproduce raw JSON verbatim — format as tables or prose
- One clarifying question per turn maximum
- If a script returns `"found": false` — say so and offer to search differently
- If a required context item is missing and cannot be defaulted — ask before running the script

[↑ Contents](#table-of-contents)

---

## 7. Subskill: Fabricator

Defined in [`instructions/fabricator.md`](instructions/fabricator.md).

Full end-to-end flow for blueprint research. Entry point when the user asks about crafting an item. This subskill orchestrates all other subskills.

### Flow

```
Step 0  (optional) faction_search.py   ← if user doesn't know which item they want
Step 1  blueprint_unlock.py            ← identify blueprint, faction, pool, standing req
Step 2  blueprint_materials.py         ← material slots, quantities, quality→stat tables
Step 3  (offer) → missions.md          ← build grind plan to earn the blueprint
Step 4  (offer) → resources.md         ← build mining route for the required materials
```

### Key Behaviors

- If `pool_size > 1`: explain the random drop pool explicitly (1-in-N chance per Master-tier run)
- If the pool contains other items: list them — the user may collect them while grinding
- Quality breakpoints presented at: Q:1, Q:250, Q:500, Q:750, Q:850, Q:1000
- For `higher_is_better: false` stats (e.g. Fuel Burn): explicitly note that lower modifier is better
- Practical quality target for most miners: B-grade (≈780–860)

### Cross-references

| Handoff | When | Target |
|---|---|---|
| Grind plan | After Step 2, if user needs to earn the blueprint | [`instructions/missions.md`](instructions/missions.md) |
| Mining route | After Step 2, if blueprint materials must be mined | [`instructions/resources.md`](instructions/resources.md) |

[↑ Contents](#table-of-contents)

---

## 8. Subskill: Missions

Defined in [`instructions/missions.md`](instructions/missions.md).

Handles faction rep grinding, rank path planning, mission filtering.

### Flow

```
Step 0  faction_search.py       ← if faction unknown, present a menu of options
Step 1  collect context          ← faction (required), current_rep (required); system, ship, party_size optional
Step 2  mission_grind_plan.py    ← tier-by-tier plan, best mission per tier
Step 3  present grind table      ← tier → next tier | runs | best mission | rep/run | UEC/hr
Step 4  (offer) → fabricator.md  ← if the grind was for a blueprint unlock
```

### Key Outputs

- Per-tier: `from_tier → to_tier`, `runs_needed`, `est_hours`, best mission title, rep/run, UEC/hr
- Totals: `total_runs`, `total_est_hours`
- `batching_notes[]` and `community_tips[]` always surfaced

### Covalex Batching (Direct Delivery)

Covalex Direct Delivery missions often share the same pickup terminal. Multiple missions can be accepted and cargo combined into one trip if: (a) same origin terminal, (b) combined SCU ≤ ship cargo, (c) destinations in the same area.

[↑ Contents](#table-of-contents)

---

## 9. Subskill: Resources

Defined in [`instructions/resources.md`](instructions/resources.md).

Handles mining location lookup, material availability, crack difficulty, route planning, and full acquisition economics.

### Flow

```
Step 1  collect context              ← materials (required), system, ship
Step 2  mining_locations.py          ← ranked locations + crack hints + recommended route
Step 3  present route                ← numbered stops with materials, risk, crack notes
Step 4  (offer) material_acquisition_plan.py
        ← collect refinery_pref and refine_what first
```

### Crack Thresholds by Ship

| Ship | Max instability | Max resistance |
|---|---|---|
| Prospector | 500 | 0.65 |
| Golem | 500 | 0.65 |
| MOLE | 700 | 0.75 |
| unknown | 400 | 0.60 |

### Refinery Preference → Method

| Preference | Recommended method | Rationale |
|---|---|---|
| `yield` | Dinyx Solventation | High yield, low cost, slow |
| `economy` | Dinyx Solventation | High yield + low fee = best net value |
| `speed` | Cormack or XCR Reaction | Fast, lower yield |
| User override | pass `--method "<name>"` | Direct override |

### Acquisition Plan Output Sections

1. **Raw ore needed** — high / medium / low yield scenarios with best refinery bonus factored in
2. **Mining trips** — worst / middle / best case for all materials combined
3. **Best refinery** — ranked by user preference with net yield % and travel time
4. **Sell prices** — live UEX prices for raw and refined forms
5. **Refining decision** (selective mode) — per-material refine / sell-raw / dump with reasoning
6. **Caveats** — yield/fee values are approximations; verify in-game before submitting

### Cross-references

| Handoff | When | Target |
|---|---|---|
| Mining solver | Material crack_assessment contains "difficult" | [`instructions/mining_solver/index.md`](instructions/mining_solver/index.md) |

[↑ Contents](#table-of-contents)

---

## 10. Subskill: Mining Solver

Entry point: [`instructions/mining_solver/index.md`](instructions/mining_solver/index.md)  
Math reference: [`instructions/mining_solver/math.md`](instructions/mining_solver/math.md)  
Output formats: [`instructions/mining_solver/output_formats.md`](instructions/mining_solver/output_formats.md)

Handles laser selection, module configuration, crackability assessment, net stat computation.

### Three Modes

| Mode | Trigger | Script invocation |
|---|---|---|
| **list** | User doesn't know their loadout | `mining_solver.py --ship <ship> --list-equipment` |
| **recommend** | "What should I use?" | `mining_solver.py --ship <ship> --rock-material <mat> --recommend` |
| **compute** | User has a specific loadout | `mining_solver.py --ship <ship> --laser <l> --modules <m1> <m2> --rock-mass <kg> --rock-material <mat>` |

### Net Stat Computation

Calibrated against the SCMDB solver at `scmdb.net/?page=solver`.

```
net_instability = rock.instability  × (1 + Σ instability_pct  / 100)
net_resistance  = rock.resistance   × (1 + Σ resistance_pct   / 100)

base_window     = gp.optimalWindowSize × gp.optimalWindowFactor        # 0.10 × 0.75 = 0.075
window_thinned  = base_window / (1 + thinness × thinness_factor × 0.1)
net_window      = window_thinned × (1 + Σ opt_window_size_pct / 100)
net_window      = min(net_window, gp.optimalWindowMaxSize)             # cap at 0.50

window_min_pct  = (midpoint - net_window / 2) × 100
window_max_pct  = (midpoint + net_window / 2) × 100
```

Full derivation with calibration example in [`instructions/mining_solver/math.md`](instructions/mining_solver/math.md).

### Difficulty Ratings

| Rating | Instability | Resistance | Window |
|---|---|---|---|
| Easy | < 200 | < 0.4 | > 12% |
| Moderate | 200–400 | 0.4–0.6 | 7–12% |
| Hard | 400–700 | 0.6–0.8 | 4–7% |
| Very Hard | > 700 | > 0.8 | < 4% |

### Ship-Specific Rules

- **Golem**: fixed Pitman laser — skip laser selection, modules only
- **MOLE multi-crew**: run solver per-laser; combined DPS = n × single laser DPS
- **Gadgets**: never recommend without asking first (default: no)

[↑ Contents](#table-of-contents)

---

## 11. Query Script Reference

All scripts in [`scripts/query/`](scripts/query/) output JSON and accept `--help`.

---

### Faction Search

[`scripts/query/faction_search.py`](scripts/query/faction_search.py)

Finds factions by system, mission type, or blueprint reward type. Agent calls this when the user has not specified a faction.

**Key args:** `--system`, `--mission-type`, `--has-blueprints`, `--blueprint-type`, `--size`, `--limit`

**Output:**
```json
{
  "count": 3,
  "factions": [
    {
      "name": "Covalex",
      "systems": ["Stanton", "Pyro", "Nyx"],
      "mission_types": ["Delivery", "Hauling", "Recovery"],
      "min_entry_tier": "Trainee",
      "max_tier": "Master",
      "tier_count": 11,
      "blueprint_pools": [ { "pool_name": "...", "blueprints": [...], "unlock_tier": "Master" } ],
      "has_blueprints": true
    }
  ]
}
```

**Inputs:** `data/missions/<version>.json`, `data/raw/<version>/merged.json`, `data/raw/<version>/crafting_blueprints.json`

---

### Mission Grind Plan

[`scripts/query/mission_grind_plan.py`](scripts/query/mission_grind_plan.py)

Tier-by-tier rep plan from current standing to a target tier. Agent calls this after collecting faction and current rep from the user.

**Key args:** `--faction`, `--current-rep`, `--target-tier`, `--system`, `--ship`, `--party-size`

**Output:**
```json
{
  "current_tier": "Rookie",
  "target_tier": "Master",
  "tiers": [
    { "from_tier": "Rookie", "to_tier": "Junior", "best_mission": { "title": "...", "rep_per_run": 100 }, "runs_needed": 2, "est_hours": 0.5 }
  ],
  "total_runs": 888,
  "total_est_hours": 89,
  "batching_notes": [...],
  "community_tips": [...]
}
```

**Inputs:** `data/missions/<version>.json`

---

### Blueprint Unlock

[`scripts/query/blueprint_unlock.py`](scripts/query/blueprint_unlock.py)

Returns faction, pool, standing requirement, and drop odds for a named blueprint. Enriches with grade and class from the SC Wiki.

**Key args:** `--name`, `--search`, `--size`, `--type`

**Output:**
```json
{
  "found": true,
  "name": "Yeager",
  "manufacturer": "Wei-Tek",
  "type": "quantumdrive",
  "grade": "A",
  "class": "Military",
  "faction": "Covalex",
  "min_tier": "Master",
  "min_rep": 237750,
  "pool_size": 9,
  "pool_blueprints": ["VK-00", "Siren", "XL-1", "Yeager", "..."],
  "expected_runs_for_this_bp": 9,
  "faction_tiers": [ { "tier": "Trainee", "min_rep": 0 }, "..." ]
}
```

**Inputs:** `data/raw/<version>/crafting_blueprints.json`, `data/raw/<version>/merged.json`, `data/wiki/*.json`

---

### Blueprint Materials

[`scripts/query/blueprint_materials.py`](scripts/query/blueprint_materials.py)

Returns material slots, quantities, and quality-to-stat breakpoints. Enriches with SC Wiki base stats where available.

**Key args:** `--name`

**Output:**
```json
{
  "name": "Yeager",
  "craft_time_seconds": 1230,
  "grade": "A",
  "class": "Military",
  "base_stats": { "performance": { "drive_speed_mms": 0.215, "cooldown_s": 4.2 } },
  "slots": [
    {
      "slot_name": "Case",
      "material": "Borase",
      "quantity_scu": 1.24,
      "stat_affected": "Integrity",
      "higher_is_better": true,
      "quality_breakpoints": [
        { "quality": 500, "modifier": 1.0, "delta_pct": 0.0, "absolute_value": 1240, "unit": "HP" }
      ]
    }
  ]
}
```

**Inputs:** `data/raw/<version>/crafting_blueprints.json`, `data/wiki/*.json`

---

### Mining Locations

[`scripts/query/mining_locations.py`](scripts/query/mining_locations.py)

Ranked mining locations for a set of materials, with crack difficulty hints calibrated to the player's ship.

**Key args:** `--materials`, `--system`, `--ship`

**Output:**
```json
{
  "ship_profile_note": "Stock Prospector — single laser, limited active modules",
  "materials": {
    "Ouratite": { "rarity": "uncommon", "instability": 600, "resistance": 0.6, "crack_assessment": "marginal — high instability...", "top_locations": [...] }
  },
  "recommended_route": [
    { "stop": 1, "location": "Lagrange A", "system": "Stanton", "overall_risk": "low", "materials_here": ["Borase", "Tungsten"], "notes": [...] }
  ],
  "warnings": [...]
}
```

**Inputs:** `data/raw/<version>/mining_data.json`

---

### Mining Solver Script

[`scripts/query/mining_solver.py`](scripts/query/mining_solver.py)

Computes net mining stats for a laser + module loadout against a target rock element. Three modes: list equipment, recommend a loadout, or compute net stats.

**Key args:** `--ship`, `--laser`, `--modules`, `--rock-mass`, `--rock-material`, `--list-equipment`, `--recommend`

**Output (compute mode):**
```json
{
  "mode": "compute",
  "net_stats": {
    "instability": 249,
    "resistance": 0.65,
    "window_size_pct": 8.5,
    "window_min_pct": 63,
    "window_max_pct": 71,
    "effective_dps": 1890,
    "difficulty": "moderate",
    "crackable": true,
    "assessment": [...]
  },
  "warnings": [...],
  "tips": [...]
}
```

**Inputs:** `data/mining/equipment.json`, `data/raw/<version>/mining_data.json`, `data/wiki/mining_lasers.json`

---

### Commodity Prices

[`scripts/query/commodity_prices.py`](scripts/query/commodity_prices.py)

Fetches **live** UEX sell prices for raw ore and refined forms of target materials. Also returns refinery methods and nearby terminals. **Called at query time — not cached.**

**Key args:** `--materials`, `--system`, `--top`, `--raw-only`

**Output:**
```json
{
  "fetched_at": "2026-06-05T12:00:00Z",
  "materials": {
    "Borase": {
      "raw":     { "best_price_sell": 28000, "terminals": [...] },
      "refined": { "best_price_sell": 33000, "terminals": [...] }
    }
  },
  "refinery_methods": [ { "name": "Dinyx Solventation", "yield": "high", "cost": "low", "speed": "slow" } ],
  "nearby_refineries": [...]
}
```

**Inputs (cached):** `data/uex/commodities.json`, `data/uex/refinery_methods.json`, `data/uex/refinery_terminals.json`  
**Live calls:** `api.uexcorp.uk/2.0/commodities_prices`

---

### Material Acquisition Plan

[`scripts/query/material_acquisition_plan.py`](scripts/query/material_acquisition_plan.py)

Full acquisition economics for a blueprint: raw ore needed per yield scenario, mining trip estimates, refinery ranking by user preference, per-material refining decision.

**Key args:** `--blueprint`, `--ship`, `--location`, `--system`, `--refinery-pref` `(nearest|yield|economy|speed)`, `--refine-what` `(all|needed|selective)`, `--method`

**Output sections:** `materials[].yield_scenarios`, `materials[].trip_scenarios`, `materials[].economics`, `total_trip_estimates`, `refineries_ranked`, `selective_refining`, `caveats`

**Inputs (cached):** `data/raw/<version>/crafting_blueprints.json`, `data/raw/<version>/mining_data.json`, `data/uex/*.json`  
**Live calls:** `commodities_prices`, `terminals_distances`

[↑ Contents](#table-of-contents)

---

## 12. Transform Script Reference

All scripts in [`scripts/transform/`](scripts/transform/). Run via [`scripts/update_cache.sh`](scripts/update_cache.sh).

---

### Transform: Missions

[`scripts/transform/missions.py`](scripts/transform/missions.py)

**Input:** `data/raw/<version>/merged.json`  
**Output:** `data/missions/<version>.json`

Denormalizes contract records. Resolves all GUID references to human-readable names. Computes `estUECPerHour` and `estRepPerHour` from `rewardUEC / timeToComplete`. Outputs `missions[]` and `legacyMissions[]` arrays.

**Key output fields per mission:** `title`, `faction`, `missionType`, `systems`, `canBeShared`, `rewardUEC`, `timeToCompleteMinutes`, `estUECPerHour`, `factionRepGain`, `estRepPerHour`, `minStanding`, `maxStanding`, `locations`, `destinations`, `shipEncounters`, `haulingOrderCount`, `isChain`

---

### Transform: Fabricator

[`scripts/transform/fabricator.py`](scripts/transform/fabricator.py)

**Input:** `data/raw/<version>/crafting_blueprints.json`, `data/raw/<version>/merged.json`  
**Output:** `data/fabricator/<version>.json`

Computes quality→modifier breakpoints at Q:1, Q:250, Q:500, Q:750, Q:850, Q:1000 using linear interpolation between `modifierAtStart`/`modifierAtEnd` ranges. Resolves faction unlock info by matching blueprint GUIDs through `blueprintPools` → `contracts`. Computes dismantle yield at ~50% efficiency, excluding blacklisted materials.

---

### Transform: Resources

[`scripts/transform/resources.py`](scripts/transform/resources.py)

**Input:** `data/raw/<version>/mining_data.json`  
**Output:** `data/resources/<version>.json`

Builds a **dual index**:
- `locations[]` — each location with all ship-minable materials and deposit probabilities
- `materials{}` — each material with all locations where it appears (sorted by probability)

Classifies location risk by type (belt/lagrange = low, moon = low-medium, planet = medium). Classifies system danger (Stanton = low, Nyx = medium, Pyro = high). Filters out FPS/hand-mining groups. Computes quality band labels (F through SS) from `qualityBandBoundaries`.

---

### Transform: Mining Equipment

[`scripts/transform/mining_equipment.py`](scripts/transform/mining_equipment.py)

**Input:** `data/raw/<version>/mining_equipment.json`  
**Output:** `data/mining/equipment.json` (overwrites on each run — version tracked inside)

Normalizes laser, module, and gadget records. Splits modules into `passive_modules` and `active_modules`. Appends ship metadata (archetype, laser slots, cargo SCU, fixed laser constraints). Preserves `globalParams` physics constants used by the mining solver math.

---

### Transform: Wiki Items

[`scripts/transform/wiki_items.py`](scripts/transform/wiki_items.py)

**Input:** `data/wiki/raw/quantum_drives.json`, `data/wiki/raw/mining_lasers.json`, `data/wiki/raw/ships.json`  
**Output:** `data/wiki/quantum_drives.json`, `data/wiki/mining_lasers.json`, `data/wiki/ships.json`

Filters to base variants only (`is_base_variant: true`). Deduplicates by name. Extracts typed sub-objects (`quantum_drive`, `mining_laser`) into flat, name-keyed output. Computes `drive_speed_mms` (Mm/s) and `disconnect_range_km` from raw SI values.

[↑ Contents](#table-of-contents)

---

## 13. Ships Modeled

| Ship | Manufacturer | Laser slots | Laser size | Cargo (SCU) | Notes |
|---|---|---|---|---|---|
| Prospector | MISC | 1 | S1 | 12 | Solo. Configurable S1 laser. |
| Golem | Drake Interplanetary | 1 | S1 | 12 | Solo. Fixed Pitman laser — modules only. |
| MOLE | Argo Astronautics | 3 | S2 | 96 | Multi-crew. Each laser independent. |

Ship stats (cargo, QD speed, fuel) come from [`data/wiki/ships.json`](data/wiki/ships.json). Mining physics (laser slots, module counts, fixed-laser constraint) come from [`data/mining/equipment.json`](data/mining/equipment.json).

[↑ Contents](#table-of-contents)

---

## 14. Patch Freshness

- `data/VERSION` holds the current patch string (e.g. `4.8.1-live.11875683`)
- Agent reads `VERSION` before every query and cites it in all answers
- If the user mentions a different patch: warn that data may be stale and suggest running `bash scripts/update_cache.sh`
- Raw data files are safe to re-fetch any time — [`scmdb_raw.py`](scripts/fetch/scmdb_raw.py) skips files that already exist for the current version

[↑ Contents](#table-of-contents)

---

## 16. Subskill: Vision — HUD Screenshot Parsing

Entry point: [`instructions/vision.md`](instructions/vision.md)  
Schema: [`schemas/vision.schema.json`](schemas/vision.schema.json)  
Scripts: [`scripts/vision/`](scripts/vision/)

Accepts a screenshot from the user (via Telegram, Discord, or direct path) and extracts structured game state from the in-game HUD without requiring a vision-capable AI model. Extraction is done with deterministic image cropping, OCR, and pixel-level colour analysis — all locally, with the image deleted after processing.

### Why no vision model

The Star Citizen HUD layout is fixed for a given 16:9 aspect ratio. Because every element appears at a predictable pixel position, we can:
1. Crop the image to the exact region of interest
2. Enhance contrast and run Tesseract OCR for text fields
3. Count HSV-matched green pixels along progress bars for percentage values

This is cheaper, faster, and keeps no image data in the LLM context window.

### Repository layout

```
scripts/vision/
├── hud_parse.py          CLI entry point: --hud <type> --image <path>
├── hud_layouts.json      Crop region definitions (fractional coords, 1920×1080 canonical)
├── calibrate.py          Visual helper: overlays regions onto a reference screenshot
└── parsers/
    ├── __init__.py
    ├── _base.py          Shared: load_and_normalise, crop_frac, enhance_for_ocr, run_ocr, measure_green_fill
    └── reputation.py     MobiGlas Reputation tab → faction, relationship, rank list, progress %
```

### Supported HUDs

| `--hud` | In-game screen | Key output fields |
|---|---|---|
| `reputation` | MobiGlas → Reputation tab (faction selected) | `faction`, `relationship`, `standing.in_progress_rank`, `standing.progress_pct`, `standing.ranks[]` |

### Pipeline

```
User sends screenshot
        │
        ▼
instructions/vision.md  ─── identify HUD type
        │
        ▼
hud_parse.py --hud <type> --image <tmp_path>
        │
        ├─ load_and_normalise()    resize to 1920×1080
        ├─ crop_frac()             cut each region per hud_layouts.json
        ├─ enhance_for_ocr()       grayscale + contrast + 3× upscale + threshold
        ├─ run_ocr()               Tesseract (single-line mode for titles)
        ├─ measure_green_fill()    HSV pixel count across bar region
        ├─ os.unlink(image_path)   image deleted here
        │
        ▼
JSON to stdout  →  agent reads and routes to missions.md / resources.md / etc.
```

### Reputation output → grind plan handoff

```json
{
  "hud": "reputation",
  "faction": "Adagio Holdings",
  "relationship": "Ally",
  "standing": {
    "in_progress_rank": "Sr. Contractor",
    "progress_pct": 42,
    "ranks": [
      { "name": "Neutral",        "state": "complete",    "progress_pct": 100 },
      { "name": "Jr. Contractor", "state": "complete",    "progress_pct": 100 },
      { "name": "Contractor",     "state": "complete",    "progress_pct": 100 },
      { "name": "Sr. Contractor", "state": "in_progress", "progress_pct": 42  }
    ]
  }
}
```

The agent maps this to `mission_grind_plan.py`:
- `--faction "Adagio Holdings"`
- `--current-rep` ≈ `tier_min + 0.42 × (tier_max − tier_min)` using the tier boundaries in `data/missions/<version>.json`

### Adding a new HUD type

1. Add a crop-region definition to `scripts/vision/hud_layouts.json`
2. Create `scripts/vision/parsers/<hud_name>.py` implementing `parse(image_path) → dict`
3. Register it in `PARSERS` dict in `scripts/vision/hud_parse.py`
4. Add the annotate branch to `scripts/vision/calibrate.py`
5. Validate with `calibrate.py --hud <name> --image <ref_screenshot>`
6. Add `--hud <name>` to the supported table in `instructions/vision.md`
7. Update this section

### Calibration

All region coordinates in `hud_layouts.json` are stored as fractions of the 1920×1080 canonical frame. To verify or tune:

```bash
python3 scripts/vision/calibrate.py --hud reputation --image my_ref_screenshot.png
# → my_ref_screenshot_annotated.png  (coloured boxes overlaid)
```

The `"_calibration_status"` key in `hud_layouts.json` is removed once a HUD's regions have been validated against a real screenshot.

### Dependencies

```
Pillow>=10.0.0
pytesseract>=0.3.10
```
System: `apt install tesseract-ocr` (Linux) / `brew install tesseract` (macOS)

[↑ Contents](#table-of-contents)

---

## 15. Future Features

The following are intentionally out of scope for the initial release. All current skill features use only public endpoints and need no setup from the user.

When implementing any of these, the UEX Bearer token goes in `.env` (gitignored). See [`.env.example`](.env.example) for setup instructions.

| Feature | UEX endpoint | Why gated |
|---|---|---|
| Blueprint ownership tracking | User account data | Requires SCMDB login + UEX sync |
| "Owned vs. unowned" blueprint display | `user_data` | Account-specific |
| Personal trade history and P&L | `user_trades` | Account-specific |
| Price submission to community DB | `post_data_submit` | Requires contributor status |
| Price alerts and watchlists | `user_notifications` | Account-specific |
| Faction reputation sync | SCMDB user profile | Requires SCMDB login |

[↑ Contents](#table-of-contents)
