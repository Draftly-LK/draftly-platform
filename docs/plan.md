# Draftly Platform — M2 Static UI Clone Plan

## Purpose

This document is the implementation plan for **milestone M2: the static UI
clone** of Draftly, built in this repo (`draftly-platform`).

> **M2 definition (from `v0-tasks.md`):** Every screen built in React with mock
> data, matched to the Harvey research screenshots; Tiptap editor with
> `FactChip`; mock types mirror the engine JSON. Feeds epics **E7** (draft
> editor & templates) and **E8** (web app), Phase 1.

M2 is the first buildable slice of the product front end. It is developed
**static-with-mocks first**, in parallel with the ML/engine work, and wired to
the real backend only in a later milestone (M3 / E8.9).

## Scope

### In scope for M2

- Every P0/P1 screen the interface spec describes, rendered with **typed mock
  data**.
- The persistent app shell (sidebar, ⌘K search, matter header, secondary nav).
- The Draftly design system (tokens, typography, density) applied faithfully.
- The Tiptap draft editor with the `FactChip` node and version pill (E7 core).
- Shared TypeScript types that **mirror the engine JSON contract**, consumed by
  every screen.
- English / Sinhala (`සිං`) interface switch scaffolding on the demo path.
- `// TODO(api):` markers at every point a real backend call will later replace
  a mock.

### Explicitly NOT in scope for M2

- No backend. No FastAPI, no database, no auth server, no real file storage.
- No real OCR / extraction / retrieval / LLM calls.
- No DOCX/PDF export engine (the export **button and approval gate** exist; the
  converter is E7.5 / later).
- No network requests. All data is local, typed, in-repo fixtures.

## Stack decision

| Layer | Choice | Rationale |
| --- | --- | --- |
| Framework | **Next.js 15 (App Router) + TypeScript** | File-based routing maps 1:1 to screens; same framework used when the backend is wired, so no rewrite; TS enforces the "mock types mirror engine JSON" requirement. |
| Styling | **Tailwind CSS** | Design tokens live in one config / CSS-vars file; fastest path to the exact Harvey-clone density and palette. |
| Components | **shadcn/ui** (Radix under the hood) | Components are copied *into* the repo and restyled to Draftly tokens — we own them. Supplies dialog, table, command palette (⌘K), tabs, tooltip, popover. The workhorse for the dense workspace. |
| Motion / flair | **Aceternity UI** (+ `motion`) | Copy-paste animated components (`ui.aceternity.com`). Used **selectively** on marketing/entry surfaces only — see the caution below. |
| Editor | **Tiptap** (ProseMirror) | Schema-validated JSON documents, custom `FactChip` node, locked prescribed-wording nodes. Mandated by E7. |
| Icons | **lucide-react** | Ships with shadcn; clean line icons matching the calm workspace look. |
| State | **Zustand** (+ URL search params) | One small store for the interactive demo state (verify/correct, simulator, audit log) with `localStorage` persistence; URL params for tabs/filters/selection. |
| i18n | **next-intl** (no-routing mode) | Cookie-based locale for the EN/සිං toggle; wired at scaffold so strings are extracted per-screen, never retrofitted. |
| Review tooling | **Playwright MCP + `@axe-core/playwright`** | Drives the AI build-review loop (screenshots, a11y snapshots, token probes, axe). |
| Fonts | **Newsreader / IBM Plex Sans / Noto Sans Sinhala** via `next/font` | Distinct legal/editorial heading voice, practical dense product UI, and proper Sinhala glyph coverage. |
| Package manager | **pnpm** | Fast, strict. Single app, so no workspace needed. |

### Aceternity UI usage boundary (important)

Aceternity components are animation- and gradient-heavy. The interface spec is
explicit: *"Do not use gradients, decorative blobs… color communicates status;
most of the interface stays neutral."* "Retint it" does not resolve that — a
spotlight or beam **is** a gradient. So the reconciliation is scope + an
explicit component list, not a caution:

- **Re-scoped mandate:** *no gradients, blobs, or decorative motion on any
  product/workspace surface.* Any gradient vocabulary is confined to
  **marketing / auth / first-run surfaces only** (regime entry, first-run
  hero).
- **Bounded entry-surface vocabulary:** single-hue, low-chroma washes derived
  from `forest`/`soft-green` at **≤ 8% alpha**. No neon, no multi-stop or
  rainbow gradients, no aurora.
- **Allowlist (retinted):** text-generate / fade-in for the wordmark; a subtle
  dot-grid or noise background.
- **Denylist:** background-beams, spotlight, aurora, meteors, glowing/gradient
  borders, decorative blobs.
- **Empty states split:** first-run/hero empty states may use the entry
  vocabulary; **in-workspace zero-states** (empty facts table,
  insufficient-authority) are plain neutral — icon + text + action, nothing
  animated beyond a reduced-motion-respecting fade.
- Components land in `frontend/src/components/aceternity/` (copied in,
  retinted to Draftly tokens).

### Backend (later milestone, recorded here for the contract)

- **FastAPI** wrapping the existing Python engine in `draftly-research`
  (`src/draftly/retrieval/`) + **PostgreSQL**. Chosen because the engine is
  already Python — FastAPI exposes it over HTTP with Pydantic models that mirror
  the frontend's `src/types` shapes.
- Wiring happens in **E8.9 / M3**, Assistant screen first (engine is ready),
  then matters + particulars, then drafts. M2 touches zero backend code.

## Repo layout

Two top-level folders, `frontend/` and `backend/`. No monorepo / workspace: the
backend is Python (FastAPI), so the TypeScript types are only ever consumed by
the one frontend app — they live inside it (`frontend/src/types`) rather than in
a separate shared package. `backend/` is created now as a placeholder and stays
empty until M3.

```text
draftly-platform/
├─ frontend/                    # Next.js 15 app (App Router)
│  ├─ src/
│  │  ├─ app/                   # routes (see Screen inventory)
│  │  ├─ components/
│  │  │  ├─ ui/                 # shadcn primitives, restyled to tokens
│  │  │  ├─ aceternity/         # Aceternity animated components (entry/hero only)
│  │  │  ├─ shell/              # sidebar, search, matter header, nav
│  │  │  ├─ matter/             # fact rows, verification controls, checks
│  │  │  ├─ assistant/          # composer, claim + citation chips, evidence
│  │  │  └─ editor/             # Tiptap wrapper, FactChip, version pill
│  │  ├─ lib/
│  │  │  ├─ mocks/              # typed fixtures (matters, facts, docs, ...)
│  │  │  ├─ store/              # Zustand demo store + audit-event bus
│  │  │  ├─ data.ts             # async accessor layer; // TODO(api): swap points
│  │  │  └─ i18n/               # next-intl messages (en.json / si.json) + enum label maps
│  │  ├─ types/                 # TS types mirroring the engine JSON contract
│  │  │  ├─ matter.ts           # Matter, MatterType, regime
│  │  │  ├─ fact.ts             # VerifiedFact, VerificationState, provenance
│  │  │  ├─ document.ts         # MatterDocument, ProcessingState, confidence
│  │  │  ├─ check.ts            # Check, CheckStatus
│  │  │  ├─ workflow.ts         # Function, Step, StepState
│  │  │  ├─ answer.ts           # GroundedAnswer, Claim, Citation, Authority
│  │  │  ├─ draft.ts            # Draft, DraftVersion, TemplateId
│  │  │  └─ index.ts
│  │  └─ styles/                # globals.css, token CSS vars
│  ├─ tailwind.config.ts
│  ├─ next.config.ts
│  ├─ tsconfig.json
│  └─ package.json
├─ backend/                     # FastAPI (M3). Placeholder until then.
│  └─ README.md                 # notes: wraps the draftly-research engine
├─ docs/
│  ├─ plan.md                   # this file
│  └─ review/                   # AI build-review loop evidence
│     ├─ _template/             # per-screen checklist template
│     ├─ _milestones/           # whole-app milestone pass artifacts
│     └─ <screen-slug>/         # baseline.png + checklist.md per screen
├─ CLAUDE.md                    # AI-agent conventions (privacy, tokens, rules)
└─ README.md
```

## Design system

All values are lifted directly from the interface spec and E8.2 and become
CSS variables + Tailwind theme tokens. **Never encode status by color alone** —
always pair color with an icon and a text label.

### Color tokens

| Token | Hex | Use |
| --- | --- | --- |
| `canvas` | `#F4F3EF` | App background |
| `surface` | `#FFFFFF` | Main work surfaces |
| `ink` | `#1B211D` | Primary text and strong actions |
| `muted-ink` | `#667068` | Metadata and secondary labels |
| `border` | `#D8DDD8` | Dividers, inputs, table rules |
| `forest` | `#24533D` | Draftly accent and verified actions |
| `soft-green` | `#E2EEE7` | Selected and verified backgrounds |
| `teal` | `#26747A` | Sources, links, corrected facts |
| `amber` | `#A56A16` | Warning **icons/fills only** — never text (see below) |
| `red` | `#A4443E` | Blocking issues and destructive actions |

No gradients, decorative blobs, or all-green screens. The interface stays
mostly neutral; color carries status.

### Derived tokens (accessibility + interaction — from the design review)

The 10 base tokens alone cannot express a dense review tool. WCAG contrast
math on the exact pairs found two failures; these derived tokens fix them and
fill the interaction-state gaps:

| Token | Hex | Why |
| --- | --- | --- |
| `amber-text` | `#8A5510` | `#A56A16` fails AA as text on white (4.49), canvas (4.05), and soft-green (3.77). All warning/conflict **text** uses this darker value; the base amber stays for icons/fills (3:1 is enough there). |
| `border-strong` | `#AEB7AE` | `#D8DDD8` is only 1.24–1.38:1 — fails the 3:1 UI-component rule. Input outlines, focused controls, and table outer frames use this; `#D8DDD8` is for interior hairlines only. |
| `selected-bg` | `#EEF2EE` | + 2 px `forest` left border. **Selection must not reuse `soft-green`** — that background means *verified*; one background carrying two meanings breaks "never status by color alone." |
| `ring` | `#26747A` | Focus ring: 2 px outline + 2 px offset, **`:focus-visible` only** (no ring on mouse click, never remove outlines). Replaces shadcn's default blue ring — a top "generic shadcn" tell. |
| `hover-bg` / `active-bg` | `#ECEBE6` / `#E4E3DD` | Neutral row/control hover and pressed states. |
| `disabled-fg` / `disabled-bg` | `#9BA39C` / `#F0EFEB` | Inactive regimes, gated export buttons. |
| `amber-bg` / `teal-bg` / `red-bg` | `#F5ECDD` / `#E1EDEE` / `#F3E3E2` | Status row tints for conflict / corrected / blocked, matching `soft-green` for verified. |
| `::selection` | `soft-green` | Text selection. |

Also: `forest-50…900` and `teal-50…900` ramps for chips/badges; smallest
metadata on `canvas` uses `#5C655E` (muted-ink passes on canvas by only 0.13 —
don't run it below 12 px there). Charts (confidence, activity): categorical
set forest → teal → amber-text → red → slate `#4A5568` + a forest sequential
ramp, CVD-checked, series always labelled.

### Typography

- Brand, major headings, matter titles, and legal-document-style headings:
  **Newsreader**.
- Interface and body: **IBM Plex Sans**, 15–16 px desktop, metadata ≥ 12 px.
- Sinhala body/UI: **Noto Sans Sinhala**. Sinhala **headings: Noto Serif
  Sinhala** — Newsreader has no Sinhala glyphs, so without it සිං headings
  silently fall back to a sans face and the serif identity dies on language
  switch.
- Per-role stacks: headings `'Newsreader','Noto Serif Sinhala'`; UI/body
  `'IBM Plex Sans','Noto Sans Sinhala'`. All four are variable fonts on
  Google Fonts, self-hosted via `next/font`.
- Per-language line-height: Latin ~1.5; **Sinhala ~1.7–1.8** (stacking
  above/below marks clip under Latin-tuned line heights).
- `font-optical-sizing: auto` globally (Newsreader is `opsz`-sensitive —
  without it, large titles render thin/text-optimized).
- **Tabular numerals (`"tnum"`) in all tables** — legal figures, dates,
  amounts must align.
- Do not make the whole app serif. Keep Newsreader for identity and
  document-like surfaces; the dense workbench stays IBM Plex Sans.
- Letter spacing: zero.
- **EN↔සිං length expansion:** no fixed-width text buttons (min-width +
  intrinsic sizing), labels may wrap to 2 lines, layouts tested at +30%
  string length.

### Shape, density, motion

- Radius: **6 px** for inputs/menus/rows/panels; **8 px max** for dialogs.
  Rigidly — no ad-hoc `rounded-full` pills except intentional status chips.
- Borders: **1 px** neutral rules; shadows only for overlays / raised composers.
  No card drop-shadows in the workspace (shadowed-white-cards-on-gray is the
  generic-SaaS silhouette we're avoiding).
- Dense review tables: **40–44 px rows** with sticky headers.
- **Spacing scale:** 4 px base — 4/8/12/16/24/32/48. Use the scale, not
  ad-hoc values.
- **Elevation:** three shadow tokens only (`--shadow-popover`,
  `--shadow-dialog`, `--shadow-toast`); z-index ladder: base 0 → sticky
  header 10 → dropdown 20 → dialog 40 → toast 50 → tooltip 60.
- **Icons (lucide):** 16 px / 1.5 stroke inline and in tables; 20 px for
  toolbar/nav; 24 px only in empty states. Default 24/2 is too heavy for
  40–44 px rows.
- **Skeletons/loading:** neutral `#ECEBE6` blocks; shimmer becomes a static
  placeholder under `prefers-reduced-motion`; document processing uses
  explicit progress states, not spinners.
- **Dark mode: light-only for M2** (explicitly). All colors are CSS variables
  so a `[data-theme]` layer can come later without touching components.
- **Print styles (legal documents get printed):** `@media print` for drafts,
  forms, checks reports, audit trail — serif body, pure black ink, app chrome
  hidden, FactChips expand to footnote/margin references, page-break rules for
  schedules, no backgrounds/shadows, status as label+icon (color may not
  survive B/W printing).
- Motion limited to panel transitions, processing progress, confirmations;
  respect reduced-motion.

### Visual identity — avoiding the generic-shadcn look

shadcn + Tailwind + lucide + a humanist sans is *precisely* the generic-SaaS
silhouette. Tokens alone won't save it; distinctiveness is engineered in.
The five moves, in leverage order:

1. **Newsreader as a real voice, not a logo font** — large matter titles,
   document/instrument surfaces, section headers in the draft editor, big
   tabular numerals, set boldly at proper optical sizes. The single strongest
   departure from the shadcn look.
2. **Bespoke verification/evidence grammar** — the five-state fact row,
   before/after correction diff, evidence-beside-fact split, pinpoint citation
   chips. No SaaS template has these; hand-build them with a ledger/marginalia
   grammar, not shadcn cards.
3. **Warm-paper / legal-ledger aesthetic** — surfaces sit on warm `canvas`
   (not white-on-cool-gray), hairline rules, a left rule/marginalia column,
   tabular figures, flat bordered surfaces. Never zinc/slate grays — only the
   warm `#D8DDD8`/`#667068` neutrals.
4. **A notarial-seal motif** — a custom stamp/seal glyph for verified state
   and authority badges (court level/type). On-theme, instantly non-generic;
   supplements lucide for these signature states.
5. **Purge the shadcn tells** — token `:focus-visible` ring instead of the
   default blue `ring-offset`; no workspace card shadows; radius rigidly
   6 px / 8 px.

## Type contract (`frontend/src/types`)

These types are the M2 contract and the target the FastAPI Pydantic models
match later. They are the "structured matter record" made concrete for the UI.

### Verification states (the core lawyer-in-the-loop states)

```ts
type VerificationState =
  | 'unreviewed'  // extracted, not yet checked by a lawyer
  | 'verified'    // lawyer confirmed against evidence
  | 'corrected'   // lawyer replaced the extracted value
  | 'conflict'    // two sources disagree
  | 'blocked';    // required evidence absent or unreadable
```

| State | Visual treatment |
| --- | --- |
| `unreviewed` | Neutral outline + pending icon |
| `verified` | Green check + reviewer/time |
| `corrected` | Blue/teal edit marker + before/after history |
| `conflict` | Amber warning + comparison action |
| `blocked` | Red issue marker + resolution action |

### Document processing states

`uploaded` → `extracting` → `ready-for-review` → `failed` (plus a
quality-problem flag). Each row shows page count, extraction confidence, and
detected quality issues.

### Other key shapes

- `Matter` — id, regime (`rta` active; `deed` / `condominium` / `special-area`
  shown but inactive), type, parties, status, created/updated.
- `VerifiedFact` — value, extracted value, source document + pinpoint location,
  confidence, `VerificationState`, reviewer, change history.
- `Check` — description, `pass | warning | fail | needs-review`, linked
  authority, resolution.
- `Step` (workflow) — ordered examination-of-title steps, per-step rules and
  keywords, `StepState`.
- `GroundedAnswer` — per-part claims, each with citation chips, authority badge
  (court level / type), and an explicit `insufficient-authority` variant.
- `Draft` / `DraftVersion` — Tiptap JSON snapshot, version hash, approval state.

### Additional types (gap-analysis additions — author these before any screen)

- `AuditEvent` — `{ id, matterId, actor, action, targetType, targetId,
  before?, after?, timestamp }`. Backs Activity/History and acceptance
  criterion #9; emitted by every store mutation.
- `User` / `Role` — reviewer/approver attribution, role-aware matter list,
  audit actor. Include notary registration/jurisdiction context.
- `Party` — matter parties (transferor/transferee etc.): role, name token,
  identity-document reference. Feeds the identity-of-parties step and Form 8
  pre-fill.
- `Obligation` — `{ id, matterId, label, dueDate, status }` for the Home
  obligations card.
- `EvidenceSpan` — the pinpoint: `{ documentId, page, region/charRange,
  snippet }`. FactChip hover, the evidence viewer, and criterion #3 all render
  from this.
- `FormTemplate` — form number, regime, ordered fields, field→fact bindings,
  locked prescribed-wording blocks, editable-region markers. Makes "encode
  Form 8 as fillable JSON" buildable.
- `CrossCheck` — the "everything must tally" reconciliation: binds N facts +
  their `EvidenceSpan`s (deed schedule ↔ survey plan ↔ municipal assessment)
  with a match/mismatch verdict. A generic `Check` cannot model this; it is
  the domain's core red-flag mechanism.
- `QuestionSet` / `Question` — the Workflows grid's question sets and the
  Library question bank.
- `DocumentVersion` — replacement history on `MatterDocument` (who replaced
  what, when, why).
- `AssistantScope` — the scope-chip model (matter / document / library).
- **Enum label maps** — every user-facing enum (`VerificationState`,
  `ProcessingState`, `CheckStatus`, `StepState`, authority levels) gets a
  typed `{ en, si }` label lookup in `lib/i18n`, not hardcoded strings.

## Mock data & interactive state

Static fixtures alone cannot demo the acceptance criteria — "verify a fact,"
"watch a document process," "record a resolution," and "inspect the audit
trail" all require **mutable client state**. The mock layer is therefore a
small state machine, not a pile of JSON:

- **Fixtures** — one anonymized demo matter (RTA, Form 8 transfer path) drives
  the whole clickable clone — never real client PII (privacy rule from the
  research repo carries over: no real names, NICs, deed/registry numbers, or
  pedigrees). Fixtures live in `frontend/src/lib/mocks/`, typed against
  `frontend/src/types`. All ids/timestamps are **fixed and seeded** — no
  `Date.now()` / `Math.random()` in render paths (hydration + demo
  determinism).
- **Mutable store** — a single **Zustand** store holds the live demo state
  (facts, documents, checks, drafts, audit log), seeded from fixtures.
  Verify / correct / resolve / approve are store actions.
- **Async accessors** — `lib/data.ts` exposes **`async` accessors returning
  `Promise<T>`** (with configurable `MOCK_LATENCY_MS`), even though data is
  local. This keeps M3's API swap from touching call sites and forces real
  loading/skeleton states now. Every accessor + action carries a
  `// TODO(api):` comment naming the future FastAPI endpoint.
- **Processing simulator** — a mock upload controller advances each uploaded
  document through `uploaded → extracting → ready-for-review` on timers
  (~1–3 s), with at least one fixture landing in `failed` and one flagged with
  a quality problem, so acceptance criterion #2 is genuinely watchable.
- **Audit-event bus** — every store mutation appends a typed `AuditEvent`; the
  Activity/History timelines render that log (seeded historical events + live
  ones from the current session). The timeline always matches what the user
  just did.
- **Persistence** — the store persists to `localStorage` (session-scoped) so a
  matter can be closed and reopened without losing context (criterion #1),
  with a visible **"Reset demo"** affordance.
- **URL state** — tab/filter/selection state lives in URL search params
  (deep-linkable, App-Router-native); Zustand holds domain state only.

## Screen inventory and routes

Routes map to the E8 task breakdown. The matter shell (`/matters/[id]`) hosts
the secondary nav: Overview · Documents · Verified facts · Workflow · Checks ·
Drafts · Activity.

| Route | Screen | Epic task | Key regions |
| --- | --- | --- | --- |
| `/` | Home | E8.3 | Wordmark, composer card, suggested notarial prompts, recent matters, obligations |
| `/new` | Create-matter stepper + regime entry | E8.8 | Four regimes (RTA active, others visible/disabled), stepper |
| `/assistant` | Global Assistant | E8.6 | Scope chips, per-part claims, citation chips, evidence pane, authority badges, insufficient-authority empty state |
| `/matters` | Matters list | E8.7 | Role-aware matter table |
| `/matters/[id]` | Matter overview | E8.1/E8.7 | Primary next action, recently verified facts, draft states |
| `/matters/[id]/documents` | Documents | E8.7 | Files table with processing states, confidence, source evidence, correction, replacement history; AT forms shown but marked unsupported |
| `/matters/[id]/facts` | Verified facts | E8.7 | Review table with the five verification states; value vs evidence; verify/correct controls; conflict comparison |
| `/matters/[id]/workflow` | Guided workflow | E8.4 | Three-pane guided run: step rail · instruction block · rules/keywords |
| `/matters/[id]/checks` | Checks | E8.8 | Check/issue rows (pass/warning/fail/needs-review), missing-document + conflict findings, resolution |
| `/matters/[id]/drafts` | Drafts list | E8.7 | Draft outputs + approval state |
| `/matters/[id]/drafts/[draftId]` | Draft editor | E8.5 / E7 | Tiptap toolbar, Revisions + Sources rails, FactChip, version pill + restore |
| `/matters/[id]/activity` | Activity | E8.8 | Audit timeline |
| `/workflows` | Workflows library | E8.4 | Grid: Functions · Draft templates · Question sets · Examples |
| `/workflows/[id]` | Guided run | E8.4 | Three-pane run screen |
| `/history` | Global History | E8.8 | Cross-matter activity timeline |
| `/library` | Library | E8.1 | Statutes, gazettes, verified case rules, question bank |
| `/settings`, `/help` | Settings / Help | E8.1 | Nav destinations |

## Component inventory

Reusable components to define (from the spec's list), each restyled to tokens:

- Global sidebar + ⌘K search; matter header + secondary nav.
- Status badge; source citation chip; authority card; evidence viewer.
- Document row + processing status; extracted-fact row; verification controls;
  conflict comparison.
- Workflow step rail; step instruction block; check/issue row.
- Assistant composer; answer with claim-level citations; insufficient-authority
  state.
- Draft editor + version selector; activity timeline; permission dialog.

**Button convention:** icon-only (with tooltip) for familiar commands
(search, upload, mic, listen, edit, download, prev/next); **text buttons for
legal decisions** (verify, approve, waive, request document, complete step).

## Tiptap editor + FactChip (E7 core in M2)

- **E7.1 Editor foundation** — Tiptap configured with schema-validated JSON;
  locked nodes for prescribed statutory wording; editable schedule/particular
  regions.
- **E7.2 FactChip node** — inline node carrying `{ fact_id, verification_state }`;
  **cannot insert an unverified fact**; hover shows source document + pinpoint.
  This is the schema-level guarantee that unverified facts never enter a draft.
- **E7.3 Versioning (UI)** — JSON snapshots, version hash shown as a version
  pill, restore + read-only previous-version banner. **Version compare is in
  scope, not stretch** — acceptance criterion #8 requires "edit, *compare*,
  approve, export." If `prosemirror-changeset` proves heavy, ship a
  two-snapshot side-by-side added/removed diff as the M2 target. Restore
  **forks a new version** (never overwrites) and emits an `AuditEvent`.
- **E7.4 Form 8 template** — encode the Form 8 (transfer) fillable JSON template
  first; Forms 9–11 later.
- **Draft generation flow (criterion #7)** — an explicit "New draft" entry
  point on the Drafts screen: template picker restricted to **approved**
  templates → pre-fill only `verified`/`corrected` facts as FactChips →
  blocked (with a clear explanation) if required facts are unverified → lands
  in the editor.
- **FactChip insertion** — inside the editor, a slash-command / Sources-rail
  picker lists only verified/corrected facts; unverified facts are not
  offered, making the E7.2 guarantee visible rather than just enforced.
- Export button + **lawyer approval gate** are present in the UI; the actual
  DOCX/PDF converter (E7.5) is out of M2 scope.

## Responsive behavior

- Primary target **1440 × 900**; minimum supported **1024 × 768**.
- At 1024 px: collapse the assistant rail by default; shorten recent-matter list.
- Below 768 px: one primary pane at a time, nav drawer, sticky bottom actions,
  full-screen evidence/draft views. Never squeeze the three-pane workflow into
  three narrow columns. Tables switch to focused row detail, not clipped text.

## Build order

Sequenced so a clickable path exists early, then screens fill in.
**i18n, keyboard/a11y, and the 1024 px layout are built into every screen as
it is made** — the late "passes" are audits, not first implementations.
Retrofitting string extraction or focus management across 17 screens is the
most expensive mistake this plan can make.

1. **Scaffold + engineering setup** — `frontend/` (Next.js 15 + TS), Tailwind,
   shadcn init, Aceternity deps (`motion`), fonts, token CSS vars;
   **`next-intl`** (no-routing mode, cookie locale); ESLint/Prettier
   (+ `prettier-plugin-tailwindcss`, `eslint-plugin-jsx-a11y`), strict
   `tsconfig`, `.gitignore`, `.gitattributes` (`eol=lf`), Node/pnpm pinning,
   CI, root `CLAUDE.md`; `error.tsx` / `not-found.tsx` / `loading.tsx`
   conventions; empty `backend/` placeholder. (E8.2 foundation + the
   Engineering setup section.)
2. **Types** — author the FULL `frontend/src/types` contract above, including
   the gap-analysis additions (`AuditEvent`, `Party`, `EvidenceSpan`,
   `FormTemplate`, `CrossCheck`, …). Close the contract before any screen.
3. **Mocks + interactive state** — anonymized RTA demo fixtures, the Zustand
   store, async accessors, the upload/processing simulator, the audit-event
   bus, `localStorage` persistence + demo reset. (The Mock data & interactive
   state section.)
4. **Shell** — sidebar (workspace mark, **Create action, matter selector**),
   ⌘K/**Ctrl+K** search over a defined corpus (matters, documents, facts,
   library entries + a static command list), matter header, secondary nav,
   routing skeleton with placeholder pages + comments. (E8.1)
5. **Home** — composer, suggested prompts, recent matters, obligations. (E8.3)
6. **Matters + Documents + Verified facts** — tables, live processing states
   (simulator), the five verification states with working verify/correct
   actions, evidence-beside-fact review, conflict comparison view,
   **failed-extraction recovery** (retry / replace / manual entry),
   replacement history. (E8.7)
7. **Workflow** — three-pane guided examination-of-title run, each step showing
   its statutory grounding (authority reference on `Step`). Build the 1024 px
   collapse behavior here, not later. (E8.4)
8. **Assistant** — claims, citation chips, evidence pane, authority badges,
   insufficient-authority state. Rail collapse at 1024 px built here. (E8.6)
9. **Draft editor** — Tiptap (client-only, dynamic import `ssr: false`) +
   FactChip + version pill + compare + restore + Form 8 template + the New
   draft generation flow. (E8.5/E7)
10. **Checks + History/Activity + create-matter stepper + regime entry** —
    checks include the `CrossCheck` tally view; Activity renders the live
    audit log. (E8.8)
11. **i18n completeness sweep** — සිං message catalogue complete on the demo
    path (EN strings were extracted per-screen from step 4 on); Sinhala legal
    terminology reviewed by the lawyer mentor; locale-aware date/number
    formatting; Sinhala rendering smoke check inside Tiptap.
12. **Responsive + a11y audit** — 1024 px full-path walkthrough, keyboard-only
    run, reduced motion, accessible labels, status never by color alone, 200%
    zoom (Sinhala QA smoke). An audit of what steps 4–10 already built.

## AI build-review loop

Every screen is built by the AI agent, then driven and reviewed through
Playwright/DevTools MCP against a checklist, fixed, and re-verified — on a
loop — before it counts as done. The AI runs the loop; the human owns the gate
at the end. Evidence is committed as the visual baseline.

### Conventions the loop assumes

- Dev server on a fixed port: `pnpm dev --port 4310`.
- Viewports: **1440×900** (primary) and **1024×768** (minimum), both captured
  every pass.
- `@axe-core/playwright` installed; axe injected on each screen.
- Evidence root: `docs/review/<screen-slug>/<YYYY-MM-DD>/`.

### 1. Per-screen loop

1. **Build** — implement/adjust the screen from the spec + tokens.
2. **Serve** — dev server up on `:4310`; navigate to the route.
3. **Drive & capture** (both viewports): screenshots; accessibility snapshot;
   console messages; network requests; axe violations; token/layout probes via
   `evaluate` (computed styles).
4. **Review** — score against the per-screen checklist. Any FAIL blocks the
   done-gate.
5. **Fix** — address every FAIL; log each in `issues.md` (found → fix →
   result).
6. **Re-verify** — re-run 3–4. Loop until all PASS or the iteration cap hits.
7. **Done-gate** — all mechanical + token + spec checks PASS, visual critique
   has no blocker, human gate cleared for flagged items.

#### Mechanical pass/fail checks

| Check | Pass condition |
| --- | --- |
| Console clean | 0 errors, 0 warnings |
| Routes healthy | this route + every link target 200 |
| No broken assets | 0 failed image/font/static requests |
| Focus traversal | Tab reaches every interactive element; visible `:focus-visible` ring |
| No horizontal overflow @1024 | every table/pane `scrollWidth <= clientWidth` |
| Reduced motion | with `prefers-reduced-motion`, no non-essential animation |
| 200% zoom no clip | no clipped/overflowing text — **Sinhala QA gate** |
| axe-core | 0 serious, 0 critical violations |

### 2. Per-screen checklist template

`docs/review/_template/checklist.md`, four blocks, every line PASS/FAIL/N/A
with an evidence pointer:

- **(a) Mechanical** — the eight checks above.
- **(b) Design-token conformance** (computed styles, not eyeballing): canvas
  `#F4F3EF` shell background; 6 px radius (≤8 px dialogs); 40–44 px rows;
  Newsreader/IBM Plex Sans/Noto Sans Sinhala actually loaded and applied;
  status never color-only (icon + label present); no gradients/blobs on dense
  workspace surfaces.
- **(c) Spec fidelity** (screen-specific), e.g. Verified facts shows all
  **five** verification states with correct treatments; Documents shows every
  processing state + AT-forms-unsupported marker; Assistant shows claim-level
  citation chips + insufficient-authority state; editor blocks unverified
  FactChip insertion.
- **(d) AI visual critique** on the screenshot: layout balance, "calm dense
  workbench" density, hierarchy, generic-shadcn-look detection. Advisory;
  only **blocker**-tagged notes fail the gate.

### 3. Loop termination & regressions

- **Cap: 3 iterations per screen**, then escalate to the human with the
  accumulated log.
- Every iteration logged in `issues.md`: failing checks, root cause, fix,
  re-verify result.
- **Regressions:** the approved screenshot per screen is committed as a
  **visual baseline**; later changes are diffed against it. After changing
  shared shell/tokens/components, re-run the mechanical + token blocks on
  nav-adjacent screens.

### 4. Milestone loops (per build-order phase)

| Pass | Method | Gate |
| --- | --- | --- |
| Acceptance walkthrough | Playwright script exercising the relevant criteria (1–10) end to end | path completes, no console errors |
| Keyboard-only run | full path via keys only (Tab/Enter/Esc/Ctrl+K) | every action reachable; focus never trapped |
| EN↔සිං toggle | toggle locale across the demo path; re-run zoom-clip probe | no clipping, no missing glyphs |
| Lighthouse | DevTools audit | **a11y ≥ 95, best-practices ≥ 95**; perf informational (dev build) |

Milestone artifacts: `docs/review/_milestones/<phase>/<date>/`.

### 5. Artifacts

- **Commit:** the final approved `baseline.png` per screen + final
  `checklist.md`.
- **Gitignore:** intermediate captures and raw probe dumps — baselines and
  checklists are the durable record.

### 6. Human gate — the loop must NOT decide alone

- **Visual identity judgment** — whether a screen "looks like Draftly";
  token deviations only as proposals.
- **Spec ambiguities** — AI proposes, human decides.
- **Legal wording** — prescribed statutory text, template copy, form labels,
  approval/waiver language. The loop verifies presence/structure; it never
  authors or alters legal wording.
- **Accepting a capped-out screen** — only on explicit human sign-off.

## Conventions

- **Static-with-mocks + comments** (your explicit rule): every screen renders
  from typed mocks; every future integration point carries a `// TODO(api):`
  comment naming the endpoint it will call.
- **Placeholders are labelled**, not silent — unsupported features (AT forms,
  inactive regimes, export converter) render but are visibly marked
  unsupported / disabled so the clone never over-claims.
- **Privacy** — demo content is anonymized/synthetic only; no real client data
  from the research repo enters this repo.
- **High model confidence is never shown as legal approval** — confidence and
  verification are distinct visuals.
- **Demo determinism** — fixtures use fixed, seeded ids/timestamps; never
  `Date.now()` / `Math.random()` in render paths (hydration mismatches, flaky
  demos).
- **Keyboard shortcuts are Windows-first** — bind **Ctrl+K** and ⌘K both; the
  team and demo machines run Windows.
- **No hardcoded UI strings** — every user-facing string goes through the
  i18n layer from the first screen onward.

## Engineering setup

Decisions the plan previously left implicit — all cheap now, expensive later:

### Repo hygiene (do at scaffold)

- **Repo stays private for M2.** The plan references Harvey (a live trademarked
  company) and the clone framing; a public "Harvey clone" repo is a
  reputational/trademark risk. If it ever goes public, scrub "Harvey" from
  committed docs first.
- **Reference screenshots are never committed** (copyright). They stay in the
  research repo or a local gitignored `references/` folder.
- **`.gitignore`** — Next defaults plus `references/`, `screenshots/`,
  `.env*`, `.next/`, `node_modules/`, and the review-loop intermediates.
- **`.gitattributes` → `* text=auto eol=lf`** + `.editorconfig` (LF, UTF-8,
  2-space) — three Windows devs on `text=auto` alone means CRLF diff storms.
- **Root `CLAUDE.md`** — carries the rules AI agents must inherit every
  session: privacy (no real PII, no committed screenshots), the token table,
  the Aceternity boundary, `// TODO(api):` convention, no-hardcoded-strings,
  demo determinism, pnpm, commit convention.
- **`.env.example`** committed from day 1 (empty for M2) to establish the
  secrets pattern before M3 needs it.

### Toolchain

- **Node pinned** — `.nvmrc` (current LTS) + `"engines"` in `package.json`.
- **pnpm pinned via Corepack** — `"packageManager": "pnpm@<version>"`;
  `pnpm-lock.yaml` committed; CI uses `--frozen-lockfile`.
- **TypeScript strict** — `"strict": true` plus `"noUncheckedIndexedAccess"`
  (critical when indexing mock fixtures) and `"noImplicitOverride"`; `@/*`
  path alias.
- **ESLint 9 flat config** — `eslint-config-next` + `@typescript-eslint` +
  **`eslint-plugin-jsx-a11y`** (a11y enforced at lint time) +
  `eslint-config-prettier`.
- **Prettier** with **`prettier-plugin-tailwindcss`** (class sorting — three
  people editing token-heavy classes).
- **Hooks** — disabled for this repo. Run `pnpm check` manually before commits
  that claim completed work. Conventional Commits with
  epic-id scopes (`feat(e8-7): …`) as a documented convention.

### CI + branching (3-person team)

- **GitHub Actions** on PR + push to `main`: install (frozen lockfile) →
  `typecheck` → `lint` → `build` → markdownlint. Branch protection: CI green +
  1 approval, squash-merge.
- **Branches** — short-lived (`feat/e8-7-facts-table`, < 2 days), named by
  epic/task id so Linear auto-links.

### Testing strategy (M2-appropriate)

- **`tsc --noEmit` is the primary gate** — the type contract is the product.
- **One Playwright smoke spec** walking the 10-criteria happy path, in CI.
- **axe assertions** inside that smoke run (via `@axe-core/playwright`).
- **One Vitest unit test on the FactChip invariant** — "cannot insert an
  unverified fact" is a logic guarantee worth locking, not just UI.
- **No Storybook** (maintenance cost > value for 3 devs). Instead a dev-only
  **`/kitchen-sink`** route rendering every component in every state — which
  also gives the review loop one URL to probe all token conformance.

### Deploy & demo

- **Vercel (Hobby) from day 1** — every PR gets a preview URL; that is how the
  lawyer mentor reviews screens continuously.
- **Symposium runs offline** — never trust venue wifi. `pnpm build && pnpm
  start` on the demo laptop is the authoritative fallback; `next/font`
  self-hosts fonts; no runtime external calls exist by design. Rehearse the
  offline build before the symposium.

### Content ownership (currently unowned — assign)

- **Synthetic evidence documents** — criterion #3 needs actual viewable source
  documents (anonymized synthetic deeds/plans/receipts, EN + සිං), rendered as
  **pre-baked page images** (no pdf.js dependency in M2). Someone must author
  these; they gate the core demo path.
- **Sinhala strings** — a native-Sinhala team member drafts; the **lawyer
  mentor reviews legal terminology** (machine translation is not acceptable
  for conveyancing terms).

## Prototype acceptance criteria

M2 (with mocks) is ready for lawyer testing when a user can:

1. Create and reopen an RTA matter without losing context.
2. Upload a small document bundle and understand every processing state.
3. Compare an extracted fact with its exact source and verify or correct it.
4. Complete an examination-of-title step with visible statutory grounding.
5. See a missing-document or conflict finding and record its resolution.
6. Ask a matter-aware question and inspect claim-level evidence or an explicit
   insufficient-authority response.
7. Generate a draft only from approved templates and verified facts.
8. Edit, compare, approve, and export a versioned draft (export is stubbed).
9. Inspect the matter audit trail for all preceding actions.
10. Complete the same core path at 1024 × 768 and with keyboard navigation.

(Criteria 1–10 are the spec's own; in M2 they are satisfied against mock data,
with #8 export stubbed behind the approval gate.)

## Out of scope / next milestones

- **M3 / E8.9** — stand up FastAPI over the Python engine; swap the mock layer
  for real calls, Assistant first, then matters/particulars, then drafts.
- **E8.10** — minimal auth, protected upload/storage, real extraction with
  evidence spans, real DOCX/PDF export.
- **E7.5 / E7.6** — export converters and Sinhala rendering QA.

## Resolved decisions

- Layout: flat `frontend/` + `backend/` (not a monorepo).
- Package manager: **pnpm** (pinned via Corepack).
- State: **Zustand** store + URL search params; async mock accessors.
- i18n: **next-intl**, no-routing mode (cookie locale), wired at scaffold.
- Version compare: in M2 scope (acceptance criterion #8), not stretch.
- Testing: typecheck gate + one Playwright smoke + axe + one FactChip unit
  test; no Storybook (dev-only `/kitchen-sink` route instead).
- Evidence rendering: pre-baked page images, no pdf.js in M2.
- Repo private for M2; reference screenshots never committed.

## Open questions

- Do we adopt shadcn wholesale or hand-build the few components that need heavy
  restyling (fact row, evidence viewer)? Leaning: shadcn for primitives,
  hand-built for the dense legal-specific components.
- Which specific Aceternity components do we want on the entry/Home surfaces
  (e.g. spotlight, background beams, text generate effect)? Pick during build so
  we retint them to Draftly tokens rather than shipping the default neon look.
- Which anonymized demo matter drives the clone — reuse the structure of the
  supervised example set (structure only, no PII) or author a fresh synthetic
  Form 8 transfer scenario?
- Who authors the synthetic evidence documents (EN + සිං), and who owns the
  Sinhala string drafting? (Lawyer mentor reviews terminology either way.)
