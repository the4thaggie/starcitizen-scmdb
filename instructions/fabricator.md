# Fabricator Subskill — Workflow

Handles: blueprint lookup, faction unlock requirements, material costs, quality-to-stat tables.
Often the entry point that then hands off to missions.md (grind) and resources.md (mining).

---

## Step 0 — If the user doesn't know which item they want

If the user says something like "what's the best craftable quantum drive?" or "what can I unlock with Covalex?", run a faction search first to show options:

```bash
# What S2 quantum drives are craftable and which faction unlocks each?
python3 scripts/query/faction_search.py --blueprint-type quantumdrive --size 2
```

Use `factions[].blueprint_pools[].blueprints[]` to list the options with faction and unlock tier, then ask the user to pick one before proceeding to Step 1.

---

## Step 1 — Identify the blueprint

Run:
```bash
python3 scripts/query/blueprint_unlock.py --name "<item_name>"
```

If the user is vague (e.g. "best S2 military quantum drive"), add filters:
```bash
python3 scripts/query/blueprint_unlock.py --search "quantum drive" --size 2 --type quantumdrive
```

**Output keys:**

| Key | Use |
|---|---|
| `found` | If `false` — tell user blueprint not found, offer to search differently |
| `found == "multiple"` | List `results[].name` and ask user to pick one |
| `name` | Confirm the blueprint |
| `manufacturer` | Include in answer |
| `type` / `subtype` | Confirm item type and size |
| `faction` | The faction whose missions unlock this blueprint |
| `min_tier` | Standing tier required to receive the blueprint |
| `min_rep` | Rep threshold for `min_tier` |
| `pool_name` | Internal pool name (informational) |
| `pool_size` | How many blueprints are in the drop pool |
| `pool_blueprints[]` | The full list of possible drops from the pool |
| `expected_runs_for_this_bp` | Equal to `pool_size` — expected Master-tier runs to get this specific blueprint |
| `faction_tiers[]` | Full standing ladder for this faction — use in grind planning |

**If `pool_size > 1`:** Explain the random drop pool explicitly:
> "The [pool_name] pool contains [pool_size] blueprints at equal weight. You have a 1-in-[pool_size] chance of getting [name] per Master-tier mission completion. Expect approximately [expected_runs_for_this_bp] runs at [min_tier] before you receive it."

---

## Step 2 — Get material requirements and quality table

Run:
```bash
python3 scripts/query/blueprint_materials.py --name "<name>"
```

**Output keys:**

| Key | Use |
|---|---|
| `craft_time_seconds` | Inform user of crafting time |
| `slots[].slot_name` | Section header for each material |
| `slots[].material` | The material needed |
| `slots[].quantity_scu` | How much to mine/buy |
| `slots[].stat_affected` | What stat this material governs |
| `slots[].higher_is_better` | If `false`, lower modifier = better (e.g. Fuel Burn) |
| `slots[].quality_breakpoints[]` | Quality-to-stat table — present as table |

**Present the quality table as:**
```
Material  │ Q:1 (min) │ Q:500 (base) │ Q:750     │ Q:1000 (max)
──────────────────────────────────────────────────────────────
Borase    │ −20% Int  │  ±0%         │ +10% Int  │ +20% Int
Tungsten  │ −20% Spd  │  ±0%         │ +10% Spd  │ +20% Spd
Ouratite  │ +20% Fuel │  ±0%         │ −10% Fuel │ −20% Fuel
```

**For `higher_is_better: false` (e.g. Fuel Burn):** a negative delta is good — make this explicit:
> "For Ouratite, lower fuel burn is better — quality 750 gives −10% (good), quality 1000 gives −20% (best)."

**Practical quality target:** After presenting the table, state:
> "For a solo Prospector miner, targeting B-grade material (quality ~780–860) is the practical ceiling. That yields roughly +10% on speed and −10% on fuel burn. SS-grade (961+) is rare and requires cherry-picking."

---

## Step 3 — Offer the grind plan

> "To earn this blueprint, you need [min_tier] standing with [faction]. Want me to build a rep grind plan from your current standing?"

If yes:
- Collect context from the user (current rep, system, ship, party size)
- Follow `instructions/missions.md` workflow, passing `--target-tier "[min_tier]"` and `--faction "[faction]"`

---

## Step 4 — Offer the mining route

> "Once you have the blueprint, you'll need to mine [list of materials]. Want a mining route?"

If yes → follow `instructions/resources.md` workflow, passing all material names.

---

## Branching rules

**If blueprint not found:**
> "I couldn't find a blueprint named '[name]'. Do you know the exact SCMDB name, or would you like me to search by type/size?"
Then re-run with `--search` and broader terms.

**If pool contains items other than the target:**
List the other items in the pool. The user may be happy to collect them too:
> "The same pool also drops: [other items]. These may be useful — you'll collect some while grinding for [name]."

**If `faction` is null (blueprint has no faction unlock):**
> "This blueprint doesn't appear to be tied to a faction mission pool. It may be unlocked through a different mechanic — check SCMDB directly for this one."

**If `note` field contains "SC Wiki API":**
> "Base item stats require the SC Wiki integration, which isn't built yet. Quality modifiers shown are percentages relative to the base — I can show you the absolute stat values once Wiki data is available."
