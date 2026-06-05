# Missions Subskill — Workflow

> [Design Doc §8](../DesignDoc.md#8-subskill-missions) · called from: [fabricator.md](fabricator.md)

Handles: mission grinding, rep planning, rank path planning, mission filtering.

---

## Step 0 — Identify the faction (if unknown)

If the user has not named a faction, do not ask an open-ended question.
Run a faction lookup first, then present a short menu.

```bash
# If system is known:
python3 scripts/query/faction_search.py --system <system> --has-blueprints

# If looking for a specific item type (e.g. from fabricator.md hand-off):
python3 scripts/query/faction_search.py --blueprint-type <type> --size <n>

# If no system or type is known yet:
python3 scripts/query/faction_search.py --has-blueprints --limit 8
```

**Output keys to use:**

| Key | Use |
|---|---|
| `factions[].name` | Faction name |
| `factions[].systems[]` | Where the faction operates |
| `factions[].mission_types[]` | What kind of work is available |
| `factions[].min_entry_tier` / `min_entry_rep` | How easy it is to start |
| `factions[].blueprint_pools[].blueprints[]` | What it unlocks |
| `factions[].blueprint_pools[].unlock_tier` | What rank is required for the reward |

Present as a compact menu:
```
Which faction would you like to grind?
1. Covalex — Delivery/Hauling in Stanton/Pyro/Nyx — unlocks QD + shields at Master
2. Ling Family Hauling — Hauling in all systems — unlocks QD + shields at Rookie
3. FTL Courier — Courier/Delivery in Stanton/Nyx — unlocks QD + power plants at Jr. Contractor
```
Then ask: "Which one, or is there a specific item you're after?"

Once the faction is chosen, proceed to Step 1.

---

## Step 1 — Collect context

Before running the grind script, you need: **faction** and **current rep**.
Collect missing items one question at a time.

| Item | How to get it | Required? |
|---|---|---|
| `faction` | From Step 0 or user input | YES |
| `current_rep` | Ask: "What is your current rep or standing name with [faction]?" | YES |
| `target_tier` | Infer from blueprint unlock data, or ask | Default: highest tier |
| `system` | Ask: "Which system are you in?" | No — default "any" |
| `ship` | Ask: "What ship are you flying?" | No — default "unknown", flag warnings |
| `party_size` | Ask: "Solo or with a group?" | No — default 1, note assumption |

If `current_rep` is given as a tier name (e.g. "Rookie"), use it as-is — the script accepts tier names.

---

## Step 2 — Run grind plan script

```bash
python3 scripts/query/mission_grind_plan.py \
  --faction "<faction>" \
  --current-rep <rep_or_0> \
  --target-tier "<tier>" \
  --system <Stanton|Pyro|Nyx> \
  --ship "<ship>" \
  --party-size <n>
```

**Output keys to use:**

| Key | Use |
|---|---|
| `current_tier` | Confirm to user: "You are currently at [tier]" |
| `target_tier` | Confirm the goal |
| `target_rep` | Total rep required |
| `tiers[].from_tier → to_tier` | One row per tier in the grind table |
| `tiers[].best_mission.title` | Recommended mission at that tier |
| `tiers[].best_mission.rep_per_run` | Rep earned per completion |
| `tiers[].best_mission.uec_per_hour` | Income while grinding |
| `tiers[].best_mission.type_note` | Community context for that mission type |
| `tiers[].best_mission.can_be_shared` | Whether it works for group grinding |
| `tiers[].runs_needed` | Runs to advance to next tier |
| `tiers[].est_hours` | Time estimate for that tier segment |
| `total_runs` | Total missions from current position to target |
| `total_est_hours` | Total time estimate |
| `batching_notes[]` | Surface all of these to the user |
| `community_tips[]` | Surface all of these to the user |

---

## Step 3 — Present the grind plan

Format as a table, one row per tier:

```
Tier          → Next Tier       | Runs | Best Mission                        | Rep/run | UEC/hr
Rookie        → Junior          |    2 | Small Covalex Shipment Recovery     |     100 | 93,000
...
```

After the table:
- State total runs and estimated hours
- List all `batching_notes` as bullet points
- List all `community_tips` as bullet points
- If `ship_cargo_scu` is null (ship unknown): note "I assumed solo with no cargo constraints. Tell me your ship for batching advice."
- If `party_size > 1`: note which missions have `can_be_shared: true`

---

## Step 4 — Offer next steps

After presenting the grind plan, offer:
> "Want me to also show the blueprint materials and a mining route for the crafting step?"

If yes → follow `instructions/fabricator.md` Step 2 (materials) and `instructions/resources.md`.

---

## Branching rules

**If the target tier is very high (total_runs > 500):**
Note the wall explicitly:
> "This is a significant grind. The [Sr. Contractor → Experienced] segment alone is ~110 runs. You may want to confirm this is the right faction before committing."

**If no missions found for a tier in the chosen system:**
The script returns `best_mission: null`. Say:
> "I couldn't find rep-granting [faction] missions in [system] at [tier]. Either missions exist in other systems, or this tier has no rep missions available. Shall I check all systems?"
Then re-run without `--system`.

**If party_size > 1 and mission has `can_be_shared: false`:**
> "Note: this mission cannot be shared. Each player must accept it individually."

**If mission has `combat: true` and party_size == 1:**
> "This mission has ship encounters. Solo without combat loadout — consider skipping to the next best option."

---

## Mission type community guidance

Surfaces from `best_mission.type_note`. Supplement with:

- **Recovery** — Fastest per run. Pickup location shown on map. No cargo capacity issues for single-item missions.
- **Direct Delivery** — Single pickup → single drop. Predictable route. Batchable when multiple missions share the same origin terminal.
- **Hauling / Bulk Haul** — Multiple pickups or large SCU. Always check total SCU against ship capacity before accepting. Covalex Bulk missions at Senior+ may require 60+ SCU ships.
- **Escort / Mercenary / Bounty** — Combat adjacent or required. Not recommended without combat loadout. Rep/hour is competitive but risk is higher.

**Batching Direct missions (Covalex-specific):**
Covalex Direct Delivery missions often share the same pickup terminal. You can accept multiple, combine the cargo into one trip if SCU allows, and deliver in one run — effectively multiplying UEC and rep per travel cycle. Only works if: (a) all missions originate from the same station, (b) combined SCU ≤ ship cargo, (c) destinations are in the same general area.
