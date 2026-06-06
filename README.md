# starcitizen-scmdb

Patch-aware Star Citizen SCMDB skill for missions, blueprints, mining, and grind planning.

## What this is

This repo packages a reusable skill that answers Star Citizen questions from local, patch-versioned SCMDB data.
It is designed to be deterministic:

- exact lookup first
- script-backed answers
- stable identifiers over fuzzy titles
- no web guessing when the local JSON already has the answer

If a question depends on SCMDB data, this skill should use the query scripts in `scripts/query/` instead of ad hoc searching.

## What it covers

- mission and reputation grind planning
- blueprint unlocks and materials
- mining locations and acquisition plans
- mining solver / loadout questions
- HUD / screenshot reading for Star Citizen UI questions

## Quick start

1. Install the skill in your framework of choice.
2. Make sure the repo is discoverable as a skill directory.
3. Ask a Star Citizen question that maps to one of the supported flows.
4. When the skill asks for an exact name or identifier, give the exact value or use the discovery/menu path first.

## Install by framework

### Hermes

Hermes discovers skills from `~/.hermes/skills/`.

Install this repo as:

```bash
mkdir -p ~/.hermes/skills/starcitizen-scmdb
cp -R <path-to-cloned-repo>/* ~/.hermes/skills/starcitizen-scmdb/
```

If you already have the repo checked out locally, point Hermes at that folder or mirror it into `~/.hermes/skills/starcitizen-scmdb/`.

### OpenClaw

OpenClaw loads skills from these locations, highest precedence first:

- `<workspace>/skills`
- `<workspace>/.agents/skills`
- `~/.agents/skills`
- `~/.openclaw/skills`

Install a local copy with:

```bash
openclaw skills install <path-to-cloned-repo> --as starcitizen-scmdb
```

For shared use across local agents:

```bash
openclaw skills install <path-to-cloned-repo> --global
```

### Claude Code

Claude Code discovers skills from:

- `<repo>/.claude/skills/<name>/SKILL.md`
- `~/.claude/skills/<name>/SKILL.md`

Recommended project install:

```bash
mkdir -p .claude/skills/starcitizen-scmdb
cp -R <path-to-cloned-repo>/* .claude/skills/starcitizen-scmdb/
```

Recommended user-global install:

```bash
mkdir -p ~/.claude/skills/starcitizen-scmdb
cp -R <path-to-cloned-repo>/* ~/.claude/skills/starcitizen-scmdb/
```

### Claude

The consumer Claude app does not use filesystem skills in the same way Claude Code does.
If you are working in Claude Code, use the install steps above.
If you are only using Claude in the web or desktop app, treat this README as the workflow reference and paste the relevant instructions into the conversation when needed.

### OpenAI Codex / Codex CLI

Codex discovers skills from repository and user locations, especially:

- `$CWD/.agents/skills/<name>/SKILL.md`
- `$REPO_ROOT/.agents/skills/<name>/SKILL.md`
- `$HOME/.agents/skills/<name>/SKILL.md`
- `/etc/codex/skills/<name>/SKILL.md` for system-wide installs

Recommended project install:

```bash
mkdir -p .agents/skills/starcitizen-scmdb
cp -R <path-to-cloned-repo>/* .agents/skills/starcitizen-scmdb/
```

Recommended user-global install:

```bash
mkdir -p ~/.agents/skills/starcitizen-scmdb
cp -R <path-to-cloned-repo>/* ~/.agents/skills/starcitizen-scmdb/
```

### OpenCode

OpenCode discovers skills from:

- `.opencode/skills/<name>/SKILL.md`
- `~/.config/opencode/skills/<name>/SKILL.md`
- `.claude/skills/<name>/SKILL.md`
- `~/.claude/skills/<name>/SKILL.md`
- `.agents/skills/<name>/SKILL.md`
- `~/.agents/skills/<name>/SKILL.md`

Recommended project-local install:

```bash
mkdir -p .opencode/skills/starcitizen-scmdb
cp -R <path-to-cloned-repo>/* .opencode/skills/starcitizen-scmdb/
```

If you already maintain Claude or agent-style skill folders, you can drop the same `SKILL.md` there instead.

## How to use it well

This skill works best when you give it exact identifiers or let it resolve them deterministically.

### Missions

Use this flow for mission and reputation questions:

- supply the faction, system, current rep, ship, and solo/group status if known
- if the faction is unknown or only partially remembered, use the faction discovery path first
- when a mission is referenced, prefer the SCMDB JSON `id`
- only attach a mission page link if the `id` ↔ URL mapping has been verified

### Blueprints and crafting

Use this flow for component unlocks and crafting questions:

- resolve the blueprint with `blueprint_lookup.py` first
- use the returned GUID for unlock and material scripts
- prefer exact blueprint names or GUIDs over partial matches

### Mining and resources

Use this flow for mining locations, solver questions, and acquisition plans:

- use exact material names in the main flow
- if you only know part of the material name, ask for the exact material or show candidate names
- use exact laser and module names in the mining solver

### Screenshots

If the user posts a screenshot, use the vision path instead of guessing.
This is especially useful for rep tiers and Career/Dossier screens.

## Best model choices

This skill is script-heavy and deterministic, so it does not need the fanciest model to be useful.
What it does need is:

- reliable tool use
- good instruction following
- long context
- strong JSON / identifier discipline
- low hallucination rate on exact names and IDs

### Best OpenRouter free options right now

Use these if your framework can point at OpenRouter.

- `openrouter/free`
  - safest default if you want the router to choose a free model that fits the task
  - good when you do not want to hardcode a provider

- `openai/gpt-oss-120b:free`
  - best general-purpose free pick for reasoning, structured answers, and tool use
  - strong choice for mission/blueprint/grind planning

- `poolside/laguna-m.1:free`
  - strongest fit for coding-agent style workflows
  - good for longer reasoning chains and tool-using tasks

- `z-ai/glm-4.5-air:free`
  - solid general agentic model
  - good balance of reasoning and responsiveness

- `nvidia/nemotron-3-super:free`
  - good general reasoning option
  - useful when you want a free fallback with broad capability

### Capability priority

For this skill, prioritize models with:

1. tool/function calling
2. 128k+ context
3. reliable structured output
4. exact name handling
5. low tendency to invent IDs or URLs

### What to avoid

Avoid tiny chat-only models for this skill if you can.
They tend to be weaker at exact identifier discipline and multi-step lookup flows.

## Repository layout

- `SKILL.md` — primary skill definition
- `instructions/` — flow-specific guidance
- `references/` — stable notes and lookup rules
- `scripts/query/` — deterministic SCMDB query helpers
- `data/` — patch-version markers and local datasets

## Troubleshooting

- If a lookup returns multiple candidates, do not guess.
- If the exact name is unknown, present a short menu.
- If a mission title is duplicated across systems, use the JSON `id` and `systems` fields to disambiguate.
- If a blueprint name is ambiguous, resolve by GUID first.
- If a material name is partial, ask for the exact mining-data name.

## UX checklist

When reviewing the skill from a new-user perspective, make sure the README answers:

- what the skill does
- where to install it for each framework
- how to invoke it correctly
- which model to use
- what to do when the exact name is unknown
- what to do when the data is ambiguous

## License

MIT
