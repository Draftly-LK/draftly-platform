# Draftly Platform — agent conventions

Rules for ALL AI agents (Claude, Codex/GPT, others) working in this repo.
The authoritative build spec is `docs/plan.md`. The UX source of truth is
`docs/reference/draftly-interface-spec.md`. Read both before writing code.

## Hard rules (never break)

- **Privacy:** never commit real client data — no real names, NICs, addresses,
  deed/registry numbers, or pedigree chains. All demo content is synthetic and
  labeled as such. Do not copy anything from `../draftly-research/data/raw/`.
- **No Harvey assets:** never commit Harvey screenshots, logos, wording, or
  other proprietary assets. This repo stays private for M2.
- **Do not modify `../draftly-research`** from sessions working in this repo.
- **Legal wording is human-owned:** never author or alter prescribed statutory
  text, form templates' legal copy, or approval/waiver language. Verify
  structure only; escalate wording to the team.

## Build conventions

- Package manager: **pnpm** (pinned via Corepack). Never npm/yarn.
- TypeScript strict; no `any` escapes without a comment justifying it.
- **No hardcoded UI strings** — every user-facing string goes through
  `next-intl` from the first screen. Enum labels come from the typed
  `{ en, si }` label maps.
- **Async mock accessors:** `lib/data.ts` functions return `Promise<T>`.
  Every accessor/action carries a `// TODO(api):` comment naming the future
  FastAPI endpoint.
- **Demo determinism:** fixtures use fixed seeded ids/timestamps. Never
  `Date.now()` / `Math.random()` in render paths.
- **Keyboard:** bind Ctrl+K and ⌘K both (Windows-first team).
- Tiptap is client-only: dynamic import with `ssr: false`.
- Commits: Conventional Commits with epic-id scopes, e.g. `feat(e8-7): …`.
- Dev server for review runs: `pnpm dev --port 4310`.

## Design system (enforced, not advisory)

- Tokens exactly as specced in `docs/plan.md` §Design system — including the
  derived tokens (`amber-text #8A5510`, `border-strong #AEB7AE`,
  `selected-bg #EEF2EE`, teal `:focus-visible` ring). No zinc/slate grays.
- Radius 6 px (8 px dialogs). 40–44 px table rows. No card shadows in the
  workspace. Icons 16 px/1.5-stroke in tables, 20 px toolbar, 24 px empty
  states.
- Fonts: Newsreader + Noto Serif Sinhala (headings), IBM Plex Sans +
  Noto Sans Sinhala (UI/body), via `next/font`. `font-optical-sizing: auto`;
  `"tnum"` in tables. Sinhala line-height ~1.7–1.8.
- **Status is never color alone** — always icon + text label.
- **Aceternity:** only on first-run/marketing surfaces, only allowlisted
  components (see plan §Aceternity boundary). Never in the dense workspace.
  Denied: beams, spotlight, aurora, meteors, gradient borders, blobs.

## Quality gates

- `pnpm typecheck`, `pnpm lint`, `pnpm build` must pass before any commit
  that claims a screen is done.
- Markdown must pass `npx markdownlint-cli2` (config at repo root).
- Follow the AI build-review loop in `docs/plan.md` for every screen; evidence
  goes to `docs/review/<screen-slug>/`. Escalate rather than self-approve the
  human-gate items.
