# starcitizen-scmdb

A simple Star Citizen helper for missions, blueprints, mining, and grind planning.

## Elevator pitch

If you want Star Citizen answers without guessing, this skill uses local SCMDB data and exact lookups.

It helps with:
- missions and reputation grind plans
- blueprint unlocks and materials
- mining spots and acquisition plans
- mining solver and loadout questions
- screenshots of Star Citizen UI

## Start here

If you are new to Linux, follow these 4 steps:

1. Open a terminal.
2. Clone the repo.
3. Copy the skill into the framework you use.
4. Ask your Star Citizen question.

### Step 1: clone the repo

```bash
cd ~
git clone https://github.com/the4thaggie/starcitizen-scmdb.git
cd starcitizen-scmdb
```

What this does:
- `cd ~` goes to your home folder
- `git clone ...` downloads the repo
- `cd starcitizen-scmdb` opens the downloaded folder

If you already cloned it before, just go to the folder you already have.

### Step 2: install the skill in your framework

Use the copy block for the framework you use below.

### Step 3: ask a question

If the skill asks for an exact name or identifier, give the exact value.
If you only know part of it, use the discovery/menu path first.

## Install by framework

Each framework below gets one copy/paste block. Assume the repo is already cloned to `~/starcitizen-scmdb`.

### Hermes

Hermes discovers skills from `~/.hermes/skills/`.

```bash
mkdir -p ~/.hermes/skills/starcitizen-scmdb
cp -R ~/starcitizen-scmdb/* ~/.hermes/skills/starcitizen-scmdb/
```

### OpenClaw

OpenClaw loads skills from its standard user skill path:

```bash
mkdir -p ~/.openclaw/skills/starcitizen-scmdb
cp -R ~/starcitizen-scmdb/* ~/.openclaw/skills/starcitizen-scmdb/
```

### Claude Code

Claude Code discovers skills from `~/.claude/skills/`:

```bash
mkdir -p ~/.claude/skills/starcitizen-scmdb
cp -R ~/starcitizen-scmdb/* ~/.claude/skills/starcitizen-scmdb/
```

### Claude

The consumer Claude app does not use filesystem skills in the same way Claude Code does.
If you are working in Claude Code, use the install step above.
If you are only using Claude in the web or desktop app, treat this README as the workflow reference and paste the relevant instructions into the conversation when needed.

### OpenAI Codex / Codex CLI

Codex discovers skills from its standard user skill path:

```bash
mkdir -p ~/.agents/skills/starcitizen-scmdb
cp -R ~/starcitizen-scmdb/* ~/.agents/skills/starcitizen-scmdb/
```

### OpenCode

OpenCode discovers skills from `~/.config/opencode/skills/`:

```bash
mkdir -p ~/.config/opencode/skills/starcitizen-scmdb
cp -R ~/starcitizen-scmdb/* ~/.config/opencode/skills/starcitizen-scmdb/
```

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

### Specific free model paths

If your framework can use OpenRouter, pick one of these exact model paths:

- `openai/gpt-oss-120b:free`
  - best general-purpose free pick for reasoning, structured answers, and tool use
  - strong choice for mission, blueprint, and grind planning

- `poolside/laguna-m.1:free`
  - strong for coding-agent style workflows
  - good for longer reasoning chains and tool-using tasks

- `z-ai/glm-4.5-air:free`
  - solid general agentic model
  - good balance of reasoning and responsiveness

- `nvidia/nemotron-3-super:free`
  - useful free fallback with broad capability
  - good when you want a second option

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
