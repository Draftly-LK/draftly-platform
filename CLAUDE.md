# Draftly Platform — agent conventions

Rules for ALL AI agents (Claude, Codex/GPT, others) working in this repo.
Frontend work follows `docs/plan.md` and
`docs/reference/draftly-interface-spec.md`. Backend work follows
`backend/backend-implementation-plan-v0.md`, `backend/docs/infrastructure.md`,
and the relevant plans under `backend/docs/services/`.

## Hard rules (never break)

- **Privacy:** never commit real client data — no real names, NICs, addresses,
  deed/registry numbers, or pedigree chains. All demo content is synthetic and
  labeled as such. Do not copy anything from `../draftly-research/data/raw/`.
- **No Harvey assets:** never commit Harvey screenshots, logos, wording, or
  other proprietary assets. This repo stays private for M2.
- **Do not modify `../draftly-research`** from sessions working in this repo.
- **Never commit or push directly to `main`.** GitHub branch protection is not
  reliable for this repo (it is a private repo owned by the `Draftly-LK`
  organization), so this rule is enforced by agents. Work on a feature branch
  (`dev/<name>/<topic>`), push that branch, and open a pull request into `main`.
  If the current branch is `main`, create a branch first. Never run
  `git push origin main`, `git push --force` to `main`, or merge into `main`
  locally. A human merges the pull request.
- **Legal wording is human-owned:** never author or alter prescribed statutory
  text, form templates' legal copy, or approval/waiver language. Verify
  structure only; escalate wording to the team.

## Backend implementation

- Backend implementation inside `backend/` is allowed when the task requests
  it. The M2 statement that no backend is in scope applies to the frontend M2
  milestone; it does not override an authorized backend task.
- Before changing backend code, read
  `backend/backend-implementation-plan-v0.md`,
  `backend/docs/infrastructure.md`, and every service plan directly affected by
  the change. Follow companion-document links when a contract crosses service
  boundaries.
- `backend/docs/**` contains approved implementation input. Agents may read it,
  implement from it, and update it when the implementation changes a documented
  API, invariant, data model, port, provider decision, or phase status.
- `backend/docs/services/**` contains sensitive, authoritative implementation
  plans. Keep them inside this private repository. Do not copy them into public
  artifacts, unrelated repositories, logs, or examples. Do not casually
  rewrite, delete, or weaken their trust boundaries and invariants.
- Open decisions and approval gates in the backend plans remain unresolved
  until the user or named owner approves them. Use local test doubles when the
  plan permits; do not silently choose a production provider or legal policy.
- Use Python 3.12 and `uv` for backend dependencies and commands. Do not manage
  backend Python packages with pnpm, npm, pip, Poetry, or an untracked virtual
  environment.
- Preserve the backend dependency direction: API routers call application
  services; application services use domain logic and ports; infrastructure
  implements ports. Domain modules do not import FastAPI, SQLAlchemy, provider
  SDKs, frontend types, or frontend fixtures.
- Original evidence is immutable. Machine derivatives and working memory are
  non-authoritative. Only lawyer-verified or lawyer-corrected facts may feed
  approved outputs. Organization and matter isolation is enforced on the
  server, and material mutations append audit events.
- The backend must not import arbitrary paths or raw data from
  `../draftly-research`. Use only an explicitly approved, versioned adapter or
  package boundary.

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
  derived tokens (`amber-text #784405`, `border-strong #A7B3C2`,
  `selected-bg #EAF0F7`, `border-control #7B8899` for input borders). Focus is a
  2 px ring with offset: navy `#1B3358` on light surfaces, gold `#C69436` on
  navy (`data-surface="inverse"`). Gold fills carry navy text, never white.
  No zinc/slate grays.
- Navy surfaces (sidebar, drawer, dashboard header, sign-in panel) share one
  backdrop: a diagonal gradient (`#1B3156` top-left, then `#0F1F38`, then
  `#0B1628`) under a faint "land parcels" texture, white 1 px lines at 7%
  forming irregular plots, as one inline SVG that scales to fit and is never
  tiled (`components/shell/navy-backdrop.tsx`). This is the only allowed
  gradient or texture; the sidebar has a 1 px right border at 8% white. Text on
  it must keep 4.5:1 on the lightest part of the gradient. No other gradients
  or decorative backgrounds.
- Radius as built, not as first specced: buttons, inputs and chips are pills
  (`rounded-control`), panels and cards 12–16 px (`rounded`, `rounded-card`),
  dialogs 16 px. 40–44 px table rows. No card shadows in the
  workspace; the one exception is the sidebar's soft lift
  (`--shadow-sidebar`, 6px 0 16px -8px at 55% navy). Icons 16 px/1.5-stroke in tables, 20 px toolbar, 24 px empty
  states.
- Fonts: IBM Plex Sans + Noto Sans Sinhala (headings and UI/body), via
  `next/font`. `font-optical-sizing: auto`;
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
- Backend changes must pass `uv lock --check`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy src`, and `uv run pytest` from
  `backend/`, limited to the gates available at the current implementation
  phase.
