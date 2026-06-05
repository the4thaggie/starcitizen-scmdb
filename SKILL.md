# starcitizen-scmdb

Answers Star Citizen questions about missions, crafting blueprints, and mining using patch-versioned data from SCMDB.net.

**Data patch:** read `data/VERSION` before any query. Cite the patch in every answer.
**Never load a full data file into context.** Always use a script from `scripts/query/`.

---

## Top-level decision tree

Read the user's request, collect missing context (ask one question at a time), then run the matching script.

---

### Branch: Blueprint + Grind + Materials + Mining
**Triggers:** user mentions a blueprint, item to craft, or rep grinding for a specific reward.

This is a multi-step flow. Load `instructions/fabricator.md` and follow its workflow.
It will also invoke `instructions/missions.md` (grind plan) and `instructions/resources.md` (mining route) as sub-steps.

---

### Branch: Missions only
**Triggers:** user asks about missions, reputation, rank grinding, or "what missions should I run."

Load `instructions/missions.md` and follow its workflow.

**Context to collect before running any script:**
| Context | Question to ask | Default if unasked |
|---|---|---|
| Faction / goal | "Which faction are you grinding, or what are you trying to unlock?" | — see faction lookup below |
| Current rep | "What is your current standing or rep score with that faction?" | Ask |
| System | "Which system are you in — Stanton, Pyro, or Nyx?" | Run for all systems |
| Ship | "What ship are you flying?" | Assume unknown, note assumption |
| Party size | "Are you running solo or with a group?" | Assume 1 |

**If faction is unknown:** Do not ask an open-ended question. First run:
```bash
python3 scripts/query/faction_search.py --system <system> --has-blueprints
```
Present the result as a short menu — faction name, what it unlocks, and what standing is required — then ask the user to pick. If the user wants a specific item type (e.g. "quantum drive"), add `--blueprint-type <type> --size <n>` to narrow it.

Collect **faction and current rep** before calling any grind script. Ship and party size can be assumed and noted.

---

### Branch: Resources / Mining locations
**Triggers:** user asks where to mine a material, best mining locations, ore concentrations, or sell prices for mined materials.

Load `instructions/resources.md` and follow its workflow.

**Context to collect:**
| Context | Question | Default |
|---|---|---|
| Target material(s) | "Which material(s) are you looking for?" | Must ask |
| System | "Which system are you currently in?" | Run all, note it |
| Ship | "What mining ship are you flying?" | "unknown" — flag capability warnings |

**Sell prices:** After presenting the mining route, offer to fetch live sell prices via `commodity_prices.py`. No token required — prices are always available.

---

### Branch: Mining solver / loadout
**Triggers:** user asks about laser selection, module configuration, rock crackability, or mining stats.

Load `instructions/mining_solver/index.md`.

---

## Stale data check

If the user mentions a patch version that does not match `data/VERSION`:
> "My data is for patch [VERSION]. You mentioned [user's patch] — answers may not reflect recent changes. Run `bash scripts/update_cache.sh` to refresh."

---

## Output rules

- Always lead with the patch version: `[Data: patch 4.8.1-live.11875683]`
- Never reproduce raw JSON verbatim — format as tables or prose
- If a script returns `"found": false` — say so and offer to search differently
- If a required context item is missing and cannot be defaulted — ask before running the script
- One clarifying question per turn maximum — do not ask multiple at once
