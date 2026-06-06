# UX install and model notes

This reference was added after user-facing README work to preserve the session learnings in a concise, reusable form.

## Install targets

- Hermes: `~/.hermes/skills/<name>/SKILL.md`
- OpenClaw: `./.agents/skills/<name>/SKILL.md`, `~/.agents/skills/<name>/SKILL.md`, `~/.openclaw/skills/<name>/SKILL.md`
- Claude Code: `./.claude/skills/<name>/SKILL.md`, `~/.claude/skills/<name>/SKILL.md`
- OpenAI Codex / Codex CLI: `./.agents/skills/<name>/SKILL.md`, `~/.agents/skills/<name>/SKILL.md`, `/etc/codex/skills/<name>/SKILL.md`
- OpenCode: `./.opencode/skills/<name>/SKILL.md`, plus Claude/agent-compatible folders

## Recommended free OpenRouter models

- `openrouter/free` — safest default router
- `openai/gpt-oss-120b:free` — best general-purpose reasoning/tool-use pick
- `poolside/laguna-m.1:free` — best coding-agent style free pick
- `z-ai/glm-4.5-air:free` — strong general agentic fallback
- `nvidia/nemotron-3-super:free` — broad free reasoning fallback

## Skill-selection preference

Prefer models with tool calling, long context, strong structured output, and low identifier hallucination.
