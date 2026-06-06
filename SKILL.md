---
name: starcitizen-scmdb
description: Use when answering Star Citizen questions about missions, crafting blueprints, or mining from patch-versioned SCMDB data. Keeps answers patch-cited, script-driven, and Hermes-native.
version: 1.1.0
author: Hermes Agent
license: MIT
category: gaming
metadata:
  hermes:
    tags: [star-citizen, scmdb, blueprints, missions, mining, hermes-native]
    related_skills: [autonomous-ai-agents/hermes-agent, software-development/hermes-agent-skill-authoring, markdown]
---

# starcitizen-scmdb

## Overview

This skill answers Star Citizen questions using patch-versioned data from SCMDB.net. It is designed to behave like a native Hermes skill: concise, script-driven, patch-aware, and explicit about what it needs before it acts.

Core rule set:
- Read `data/VERSION` before any query.
- Never load a full data file into context.
- Use scripts under `scripts/query/` for all real lookups.
- Lead every final answer with the patch version.
- Ask at most one clarifying question per turn.

## When to Use

Use this skill when the user asks about:
- Missions, reputation, rank grinding, or faction unlocks
- Crafting blueprints, component unlocks, or "best X for my ship" questions
- Mining locations, ore/material availability, or commodity sell prices
- Mining solver / loadout questions about laser selection or crackability
- Screenshot-based HUD inspection for Star Citizen UI questions

Do not use this skill for unrelated game chat or generic web research unless the answer depends on SCMDB data.

## Hermes-Native Routing Rules

1. **Patch first.** Read `data/VERSION` before anything else.
2. **Script only.** Never paste full data files or raw JSON into the chat.
3. **One question at a time.** If required context is missing, ask the minimum question needed.
4. **Search before repeat.** If the user refers to prior Star Citizen work in this thread, use session recall before making them restate it.
5. **Cite the patch.** Every answer starts with the data version.

## Decision Tree

### Blueprint + Grind + Materials + Mining

**Triggers:**
- "best components for [ship]"
- "what's the best [weapon/shield/qd/cooler/powerplant] for my [ship]"
- blueprint / crafting / unlock / reward queries
- rep grinding for a specific reward

This is a multi-step flow. Load `instructions/fabricator.md` and follow it end to end.
It orchestrates the supporting flows in `instructions/missions.md` and `instructions/resources.md`.

**Workflow:**
1. Identify the ship's component sizes first.
2. Search blueprints with `scripts/query/blueprint_unlock.py` using `--type` and `--size`.
3. Use `scripts/query/blueprint_materials.py` for material requirements.
4. Build the grind plan with `scripts/query/mission_grind_plan.py`.
5. If materials require mining, route through `scripts/query/mining_locations.py` and `scripts/query/material_acquisition_plan.py`.

**Never skip `fabricator.md`** — it is the orchestrator for the full chain.

### Missions Only

**Triggers:**
- "what missions should I run"
- reputation or rank grinding without a specific item target

Load `instructions/missions.md`.

Collect these before running a grind script:
- Faction / goal: "Which faction are you grinding, or what are you trying to unlock?"
- Current rep: "What is your current standing or rep score with that faction?"
- System: "Which system are you in — Stanton, Pyro, or Nyx?"
- Ship: "What ship are you flying?"
- Party size: "Are you running solo or with a group?"

If the faction is unknown, do **not** ask an open-ended question. First run:

```bash
python3 scripts/query/faction_search.py --system <system> --has-blueprints
```

Then present a short menu with:
- faction name
- what it unlocks
- standing required

If the user wants a specific item type, narrow it with `--blueprint-type <type> --size <n>`.

### Resources / Mining Locations

**Triggers:**
- where to mine a material
- best mining locations
- ore concentrations
- sell prices for mined materials

Load `instructions/resources.md`.

Collect these before running a mining query:
- Target material(s): "Which material(s) are you looking for?"
- System: "Which system are you currently in?"
- Ship: "What mining ship are you flying?"

Use:
- `scripts/query/mining_locations.py` for route/location results
- `scripts/query/commodity_prices.py` for sell prices
- `scripts/query/material_acquisition_plan.py` when the user wants the full acquisition loop

### Mining Solver / Loadout

**Triggers:**
- laser selection
- module configuration
- rock crackability
- mining stats

Load `instructions/mining_solver/index.md` and answer from there.

### HUD Screenshot

**Triggers:**
- user uploads a screenshot/photo/image
- user says "look at this" / "here's my screen" / "I took a screenshot"
- an image file path appears in the message context

Load `instructions/vision.md` and follow its intake + routing workflow.

## Output Rules

- Always lead with the patch version, e.g. `[Data: patch 4.8.1-live.11875683]`
- **Size context is mandatory.** Every blueprint recommendation MUST include `size` (S1/S2/S3/etc.) and MUST match the user's ship slot size.
- **Never cross-size suggestions.** Do not recommend S2 components for S3 grind requests, or vice versa.
- Never reproduce raw JSON verbatim; format as prose or bullets
- Pool alternatives MUST show size info: `{"name": "TS-2", "size": "size3", "type": "quantumdrive"}`
- If a script returns `found: false`, say so and offer a narrower search
- If required context is missing and cannot be defaulted, ask before running the script
- Keep answers concise and actionable

## Size Enforcement Rules

When presenting blueprint alternatives or pool drops:

1. **Always identify ship component size first.** S1 (small), S2 (medium), S3 (large), S4 (extra-large).
2. **Filter all blueprint queries by size.** Use `--size <n>` parameter in all lookup scripts.
3. **Label pool alternatives with their size.** The `pool_blueprints` array now includes `{"name", "size", "type"}` objects.
4. **Cross-reference ship configs.** See `references/s1-components.md` and `references/s3-components.md` for size-appropriate options.
5. **Reject mixed-size pools.** If a faction pool contains multiple sizes, present them separately or ask the user to specify.

**Example size matching table:**
- S1 slot: Prospector, Aurora MR/CL/ES/LX, Reliant Kore
- S2 slot: Freelancer, Cutlass Black, Vanguard
- S3 slot: Constellation, Cutter, Merchantman, MOLE, Caterpillar
- S4 slot: 600i, 890 Jump, Pegasus

## Common Pitfalls

1. **Wrong branch selection**
   - "Best components for [ship]" belongs in the Blueprint + Grind branch, not Missions only.

2. **Skipping fabricator.md**
   - Blueprint / grind questions need the full fabricator chain.
   - Skipping it usually loses material requirements or the actual unlock path.

3. **Forgetting ship size filters**
   - Always filter blueprint searches by ship component size.
   - Use `--size <n>` and `--type <type>` together whenever possible.

4. **Asking open-ended faction questions**
   - If the faction is unknown, show a menu from `faction_search.py` instead of asking "which faction?".

5. **Dumping script output verbatim**
   - Convert the result into a readable menu, table, or bullet list.

## Verification Checklist

- [ ] Frontmatter starts at byte 0 and parses cleanly
- [ ] `name`, `description`, `version`, `author`, `license`, and `metadata.hermes` are present
- [ ] File remains under the skill size limit
- [ ] `data/VERSION` is read before any query path
- [ ] `scripts/query/` is the only data-access path used
- [ ] Source copy and local mirror match exactly
