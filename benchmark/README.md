# SCMDB Agent Benchmark

A YAML benchmark for choosing the **best model to run the `starcitizen-scmdb` skill**.
You run a model as the SCMDB agent inside a Telegram chat, export the conversation,
and an automated LLM judge scores it against per-case rubrics. Higher accuracy &
discipline → higher score.

## What's being tested

The model-under-test acts **as the SCMDB skill agent**, replying to a human in
Telegram. Each test case feeds it a realistic player message (slang, typos, missing
context) and checks whether it:

1. **Routes** to the correct `SKILL.md` branch (missions / resources / mining-solver /
   fabricator / vision).
2. **Interprets human-speak** — expands slang (`quant`→Quantainium, `QD`→quantum drive),
   tolerates typos, extracts the right entities.
3. **Gathers required context** before acting, defaults the optional bits (and says so),
   and asks **one question per turn**.
4. **Follows the workflow** — the prescribed steps, scripts, and branching rules
   (Golem fixed laser, MOLE operator count, drop-pool randomness, found:false, …).
5. **Surfaces accurate, script-grounded data** — no invented factions, locations,
   prices, or capabilities.
6. **Obeys output rules** — lead with the patch line, tables not raw JSON, required
   disclaimers.

## Layout

```
benchmark/
  spec.yaml              # the scoring ENGINE (model- & case-agnostic)
  cases/
    missions.yaml        # 3 cases
    resources.yaml       # 3 cases
    mining_solver.yaml   # 3 cases
    fabricator.yaml      # 2 cases (hardest branch, weighted 1.25)
    vision.yaml          # 3 cases  (HUD screenshots — user turn carries a `photo`)
    cross_cutting.yaml   # 5 cases  (staleness, output rules, multi-intent, slang, scope)
  exports/
    SAMPLE_missions-001.json   # example Telegram export in the graded format
```

## How scoring works (`spec.yaml`)

- **6 weighted dimensions**, each scored 0.00–1.00 by the judge:
  `routing, human_speak, context_gathering, workflow_adherence, data_fidelity, output_compliance`.
  `raw = Σ(dimension × weight)`. A case may re-weight or drop dimensions.
- **Hard gates** apply *after* the weighted sum — caps or penalties for the
  non-negotiables: missing patch line (`cap 0.60`), raw-JSON dump (`cap 0.50`),
  hallucinated data (`zero data_fidelity + cap 0.40`), >1 question per turn
  (`−0.15`), running a script before required context, open faction question where a
  lookup is required, fabricated capability, claiming to store a screenshot.
- **Per-case final** = `clamp(min(raw, caps) − penalties, 0, 1)`.
- **Suite score** = case-weighted mean, where
  `case_weight = category_weight × difficulty_multiplier` (easy 1.0 / medium 1.5 / hard 2.0).
- **Weighting profiles** (`balanced`, `accuracy_first`, `conversation_first`,
  `production_strict`) let you re-rank models for different priorities without editing cases.

### The key constraint: judge sees CHAT ONLY

The Telegram export contains the agent's **messages**, not its tool calls. So every
rubric item is written to be **observable from chat text**, and each case carries a
`ground_truth` block (real factions, materials, ship facts, required disclaimers)
that the judge checks the agent's stated values against. Workflow steps are inferred
from what the agent says (e.g. a faction *menu* implies the faction lookup ran; a
quality *table* implies `blueprint_materials` ran).

## Running a model through the benchmark

1. **Generate transcripts.** Drive the candidate model as the SCMDB agent in Telegram
   (or any harness that produces the same JSON shape) for each case's
   `scenario.seed_messages` + `scripted_followups`. Export chat history as JSON into
   `exports/<model>__<case_id>.json`. Vision cases need a `photo` attachment on the
   triggering user turn.
2. **Set agent identity.** In `spec.yaml` → `telegram_export.agent_identity`, set the
   bot's `from_id` (and display-name fallback) so the judge knows which turns are the
   agent's. (The sample export carries this under `_benchmark_meta` for convenience.)
3. **Judge each export.** Give an automated judge (strong reasoning model, temp 0)
   `spec.yaml` + the single case entry + the one export, following
   `spec.yaml → judge_protocol`. It emits a result per `result_schema` (final score,
   per-dimension scores with cited message ids, gate trips, critical-check pass/fail).
4. **Aggregate.** Combine per-case results per `suite_scoring` into the model's
   headline score + per-category / per-dimension / gate-trip breakdowns. Repeat under
   each weighting profile you care about. Compare models.

## Maintaining the benchmark

- Cases are anchored to skill `file:line` (e.g. `missions.md:9-13`). When the skill's
  workflows change, update the anchored cases.
- When the data cache is refreshed to a new patch, bump
  `meta.target_skill_version_pin` and the `patch_line_required` / `ground_truth`
  values that reference specific factions, materials, or prices.
- Add new SC slang to `spec.yaml → glossary` as it shows up in real chatter; the
  `human_speak` dimension credits correct expansion.
- Add cases by copying an existing one — the case schema is documented at the top of
  each `cases/*.yaml` file. Keep every rubric item **chat-observable** and back every
  concrete claim with a `ground_truth` entry.

## Current coverage

19 cases across 6 categories and 3 difficulty levels, covering every `SKILL.md`
branch plus the cross-cutting behaviors (version staleness, output rules, multi-intent
routing, human-speak stress, and out-of-scope honesty). Extend freely.
