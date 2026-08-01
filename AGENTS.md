# Agents

All agent conventions for this repository live in [CLAUDE.md](CLAUDE.md) —
they apply to every AI agent (Codex/GPT, Claude, and others), not only Claude.

Read [CLAUDE.md](CLAUDE.md) before changing code or implementation docs.

For frontend work, then read:

1. [docs/plan.md](docs/plan.md) — the authoritative M2 implementation plan.
2. [docs/reference/draftly-interface-spec.md](docs/reference/draftly-interface-spec.md)
   — the UX source of truth (screens, states, behavior).

For backend work, then read:

1. [backend/backend-implementation-plan-v0.md](backend/backend-implementation-plan-v0.md)
   — the authoritative backend plan.
2. [backend/docs/infrastructure.md](backend/docs/infrastructure.md) — database
   and storage decisions.
3. Every relevant plan in [backend/docs/services](backend/docs/services) before
   changing that service or one of its contracts.

Repository-local skills live under `.agents/skills/`. Use
`avoid-ai-writing` when its trigger description matches the user's request.
