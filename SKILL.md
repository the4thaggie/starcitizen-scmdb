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
- Keep `README.md` current as the user-facing install/use/model guide; see it first when asked how to install or choose a model.
- See `references/ux-install-models.md` for a compact install/model cheat sheet.

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
6. **Exact-match links.** When linking missions, use the explicit JSON `id` and verify the exact title/system pair before attaching a URL. See `references/mission-linking.md`.
7. **Exact blueprint identity.** Resolve blueprints with `scripts/query/blueprint_lookup.py` first, then pass the resulting `guid` to unlock/material/planning scripts. See `references/deterministic-lookup.md`.

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
2. Resolve the blueprint with `scripts/query/blueprint_lookup.py` using exact `--guid` or exact `--name`.
3. Use `scripts/query/blueprint_unlock.py` and `scripts/query/blueprint_materials.py` with the resolved `--guid`.
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

If the faction is unknown or only partially remembered, do **not** ask an open-ended question. First run:

```bash
python3 scripts/query/faction_search.py --system <system> --has-blueprints
```

Then present a short menu with:
- faction name
- what it unlocks
- standing required

If the user already knows the exact faction name, use `--name <exact>` instead of keyword guessing.
If the user wants a specific item type, narrow it with `--blueprint-type <type> --size <n>`.

### Resources / Mining Locations

**Triggers:**
- where to mine a material
- best mining locations
- ore concentrations
- sell prices for mined materials

Load `instructions/resources.md`.
See `references/material-lookup.md` for the exact-name / canonicalization rules.

Collect these before running a mining query:
- Target material(s): "Which material(s) are you looking for?" Use exact material names from mining data.
- System: "Which system are you currently in?"
- Ship: "What mining ship are you flying?"

Use:
- `scripts/query/mining_locations.py` for route/location results
- `scripts/query/commodity_prices.py` for sell prices
- `scripts/query/material_acquisition_plan.py` when the user wants the full acquisition loop

If the user only knows part of a material name, present a short candidate menu instead of guessing.

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
Use `references/rep-tier-screenshot-notes.md` when the image is a Career/Dossier rep screen so you can read the exact highlighted tier instead of estimating from a vague rep range.

### Rep estimate from screenshots

If the user gives a screenshot of the Career/Dossier ladder:
- read the highlighted tier directly
- distinguish the overall faction label from the specific progression track
- treat the highlighted track as the current standing for grind planning

Do not ask for a numeric rep estimate when the screenshot already shows the tier name clearly.

## Output Rules

- Always lead with the patch version, e.g. `[Data: patch 4.8.1-live.11875683]`
- Never reproduce raw JSON verbatim; format as prose or bullets
- If a script returns `found: false`, say so and offer a narrower search
- If required context is missing and cannot be defaulted, ask before running the script
- Keep answers concise and actionable
- Prefer deterministic JSON records and stable identifiers over web search or snippet matching
- When a blueprint is referenced, include the SCMDB GUID whenever available
- When a mission is referenced, include the SCMDB JSON `id` whenever available
- See `references/deterministic-lookup.md` for the exact-match policy across missions, blueprints, and mining equipment
- Only present a mission page link if the exact `id` ↔ URL mapping has been verified from deterministic data
- Never use web search or browser lookups to identify a mission when the local SCMDB JSON already contains the record

## Common Pitfalls

1. **Wrong branch selection**
   - "Best components for [ship]" belongs in the Blueprint + Grind branch, not Missions only.

2. **Skipping fabricator.md**
   - Blueprint / grind questions need the full fabricator chain.
   - Skipping it usually loses material requirements or the actual unlock path.

3. **Forgetting exact blueprint identity**
   - Resolve blueprints with `blueprint_lookup.py` first.
   - Pass the resulting `guid` to unlock/material/planning scripts.
   - Avoid partial-name matching in the main flow; it is only a fallback for vague menu generation.

4. **Forgetting ship size filters**
   - Always filter blueprint searches by ship component size when you are in a menu-generation branch.
   - Use `--size <n>` and `--type <type>` together whenever possible.

5. **Mining solver fuzzy matching**
   - Treat `--laser`, `--modules`, and `--rock-material` as exact names in the main flow.
   - If the user doesn't know the exact name, send them to `--list-equipment` or present a menu first.

6. **Asking open-ended faction questions**
   - If the faction is unknown, show a menu from `faction_search.py` instead of asking "which faction?".

7. **Dumping script output verbatim**
   - Convert the result into a readable menu, table, or bullet list.

8. **Link/title mismatches**
   - Never attach a URL to a mission title unless that exact title appears in the lookup result *and* the system/variant matches.
   - If search snippets return multiple similar missions or system variants, do not guess which URL belongs to which title.
   - Prefer `scripts/query/mission_lookup.py` for identity checks; only fall back to page verification if local data is insufficient.
   - If exact pairing cannot be confirmed, say so and return the exact record fields (`id`, `title`, `systems`, `debug_name`) without a link.

9. **Duplicate titles are normal**
   - Treat repeated mission titles across Stanton/Nyx/Pyro as expected, not exceptional.
   - Use `id` + `systems` to disambiguate before any link or recommendation.

10. **Do not silently collapse candidate menus**
   - If a helper returns candidate names or multiple exact-looking variants, do not pick one implicitly.
   - Present the candidates or ask for the exact identifier, then continue with the exact lookup path.

## Verification Checklist

- [ ] Frontmatter starts at byte 0 and parses cleanly
- [ ] `name`, `description`, `version`, `author`, `license`, and `metadata.hermes` are present
- [ ] File remains under the skill size limit
- [ ] `data/VERSION` is read before any query path
- [ ] `scripts/query/` is the only data-access path used
- [ ] Source copy and local mirror match exactly
