# Draftly UI refinement: final report

Branch `platform/ui-refine-praveen`, brief `DRAFTLY_UI_REFINEMENT.md`. This is a
presentation-layer change: no business logic, data fetching, API routes,
database schema, auth logic or URLs changed. Sinhala strings for native-speaker
review are in [sinhala-review.md](sinhala-review.md).

## What was done, by phase

| Phase | Result |
| --- | --- |
| 0. Audit | Stack, tokens, hard-coded values and components inventoried; 16 "before" screenshots. |
| 1. Tokens | One token set; navy and gold focus rings; closed type scale; no card shadows; no entrance animation; sentence case. |
| 2. Components | Button states, Input, Select, Textarea, StatusChip, Card, EmptyState, SectionHeader, Divider, Menu, ListRow. |
| 3. Shell | Grouped sidebar, account menu in the footer, quieter search, dev badge moved. |
| 4. Dashboard | Compact header, counts row, matters list, obligations, workflow cards, first-run state. |
| 5. Sign-in and sign-up | Split screen, shared Clerk appearance built on tokens. |
| 6. Consistency | Matters URL filters, skeletons, empty and error states on six pages. |
| 7. Responsive and accessibility | Drawer below 1024px, stacked rows, axe audit at three widths. |
| Follow-up | Billing, Settings and Help moved into the account menu (Profile, Settings, Billing, Help, divider, Sign out); themed thin scrollbars without arrow buttons. |

## Files changed

`136` files against the branch base, `6177ea6f78990ba12450621f1979ec1d80a96ceb`. By area:

- **Screenshots and reports (docs/review/ui-refine)**: 42
- **Page screens (matter, assistant, library, activity, support and others)**: 31
- **Shared components (components/ui)**: 16
- **Dashboard (components/home, lib/home)**: 14
- **Sign-in, sign-up, Clerk (components/auth, app/sign-*, lib/auth, layout)**: 10
- **App shell (components/shell)**: 8
- **Other**: 6
- **Tokens and config (globals.css, tailwind, next config, utils)**: 5
- **Strings (en.json, si.json)**: 2
- **CLAUDE.md**: 1
- **E2E specs**: 1

The full list is `git diff --name-status 6177ea6..HEAD`.

## Final token values

Defined once in `frontend/src/styles/globals.css` (`:root`), mirrored in
`frontend/tailwind.config.ts`. Radius is unchanged from before this work, by
decision: controls are pills (`rounded-control`), containers 16px
(`rounded-card`), the default `rounded` is 12px.

```css
:root {
  /* "Trust & authority" palette (docs/review/ui-refresh): authority navy with a
     restrained gold accent, cool neutral canvas, status hues unchanged.
     Asserted by tests/e2e/design-audit.spec.ts â€” change both together. */
  --canvas: #f3f5f8;
  --surface: #ffffff;
  --ink: #0f1b2e;
  --muted-ink: #566377;
  --border: #dce2ea;
  --border-strong: #a7b3c2;
  /* Boundary of an input, select or textarea: 3.3-3.6:1 on surface, canvas and
     hover fills (WCAG 1.4.11). --border-strong is 2.1:1 and stays decorative. */
  --border-control: #7b8899;
  --forest: #1b3358;
  --soft-green: #e7eef8;
  --teal: #176b75;
  --amber: #9c5b0b;
  --amber-text: #784405;
  --red: #a43d45;
  --red-hover: #8b323a;
  --selected-bg: #eaf0f8;
  /* Focus: navy on light surfaces, gold on navy (data-surface="inverse").
     Navy is 11.6:1 on the canvas; gold is 5.2-6.6:1 on the navy ramp. */
  --ring: #1b3358;
  --ring-on-dark: #c69436;
  --hover-bg: #eef2f7;
  --active-bg: #e2e8f0;
  --disabled-fg: #929dac;
  --disabled-bg: #eef1f5;
  --amber-bg: #f8ead5;
  --teal-bg: #e0eef0;
  --red-bg: #f5e3e5;
  /* Brand chrome: the navigation rail and hero bands sit on navy; gold marks
     the one primary action and the current place, never status. */
  --navy-950: #0b1628;
  --navy-900: #0f1f38;
  --navy-800: #172b4b;
  --gold: #c69436;
  --gold-strong: #74510f;
  --gold-soft: #f6eedc;
  /* Gold fills carry navy text (6.6:1). White on gold is 2.7:1 and fails. */
  --gold-hover: #b78628;
  /* Success was the one status hue the palette lacked. */
  --success: #1f6b3a;
  --success-bg: #e4f1e8;
  /* Semantic names. They alias the values above, so each value is defined
     once and components may use either name. */
  --bg: var(--canvas);
  --surface-inverse: var(--navy-900);
  --text-primary: var(--ink);
  --text-secondary: var(--muted-ink);
  --text-muted: var(--muted-ink);
  --text-on-inverse: var(--on-dark);
  --accent: var(--gold);
  --accent-hover: var(--gold-hover);
  --accent-subtle: var(--gold-soft);
  --focus-ring: var(--ring);
  --warning: var(--amber-text);
  --warning-bg: var(--amber-bg);
  --danger: var(--red);
  --danger-bg: var(--red-bg);
  --info: var(--teal);
  --info-bg: var(--teal-bg);
  /* Amber for warnings on navy: --amber-text (2.1:1) is for light surfaces. 8:1 on navy-900. */
  --amber-on-dark: #f2a541;
  --sidebar-width: 244px;
  /* On-dark surface. The first-run hero sits on a photograph, and without
     these every dark surface reaches for literal white.
     Composed from the tokens above rather than written as fixed hexes, so
     retinting the palette retints this too. */
  --on-dark: var(--canvas);
  --on-dark-muted: color-mix(in srgb, var(--canvas) 68%, var(--muted-ink));
  --panel-dark: color-mix(in srgb, var(--ink) 72%, transparent);
  --border-on-dark: color-mix(in srgb, var(--canvas) 22%, transparent);
  --scrim: color-mix(in srgb, var(--ink) 55%, transparent);
  --shadow-popover: 0 8px 24px rgb(15 27 46 / 0.12);
  --shadow-dialog: 0 16px 48px rgb(15 27 46 / 0.16);
  --shadow-toast: 0 6px 20px rgb(15 27 46 / 0.14);
}
```

Type scale, closed: 12, 13, 14, 16, 18, 20, 24 and 30px with set line heights.
Body text is 14px. In Sinhala the scale is multiplied by 1.14 (body 16px) and
line height by 1.25, through `--type-scale` and `--lh-scale`; the Sinhala
sidebar is 272px wide instead of 244px. English renders exactly as written.

Spacing is the Tailwind 4px scale. Shadows: only popover, dialog and toast
remain. Motion: 150ms ease-out on colour, background and border only;
`prefers-reduced-motion` is honoured globally and the skeleton pulse only runs
when motion is allowed.

Contrast, measured: navy focus ring 11.6:1 on the canvas; gold focus ring
5.2 to 6.6:1 on the navy ramp; navy text on gold fill 6.6:1 (white on gold is
2.7:1 and is not used); input border 3.3 to 3.6:1; on-dark amber 8:1 on navy.

## Screenshots

Before: `docs/review/ui-refine/before/` (1440px, English and Sinhala, taken
before any change). After: `docs/review/ui-refine/after/`.

| Page | Before | After |
| --- | --- | --- |
| Sign-in | [en](before/en-sign-in.png), [si](before/si-sign-in.png) | [en](after/en-sign-in.png), [si](after/si-sign-in.png) |
| Dashboard | [en](before/en-dashboard.png), [si](before/si-dashboard.png) | [en](after/en-dashboard.png), [si](after/si-dashboard.png) |
| Matters | [en](before/en-matters.png), [si](before/si-matters.png) | [en](after/en-matters.png), [si](after/si-matters.png) |
| Research | [en](before/en-research.png), [si](before/si-research.png) | [en](after/en-research.png), [si](after/si-research.png) |
| Legal sources | [en](before/en-legal-sources.png), [si](before/si-legal-sources.png) | [en](after/en-legal-sources.png), [si](after/si-legal-sources.png) |
| History | [en](before/en-history.png), [si](before/si-history.png) | [en](after/en-history.png), [si](after/si-history.png) |
| Billing | [en](before/en-billing.png), [si](before/si-billing.png) | [en](after/en-billing.png), [si](after/si-billing.png) |
| Settings | [en](before/en-settings.png), [si](before/si-settings.png) | [en](after/en-settings.png), [si](after/si-settings.png) |

Mobile and tablet (after only): [dashboard 390](after/en-dashboard-390.png),
[matters 390](after/en-matters-390.png), [sign-in 390](after/en-sign-in-390.png),
[drawer open 390](after/en-drawer-open-390.png),
[dashboard 768](after/en-dashboard-768.png), plus the Sinhala
[dashboard 768](after/si-dashboard-768.png),
[dashboard 390](after/si-dashboard-390.png) and
[matters 390](after/si-matters-390.png).

All screenshots use synthetic demo data. The Sinhala shots were taken with the
Sinhala locale switched on locally; it is off in the product (see below).

## Verification

- `pnpm typecheck`, `pnpm lint`, `pnpm build` pass; `pnpm test:coverage` passes
  (the `src/lib` threshold included). Markdown passes `markdownlint-cli2`.
- axe (WCAG 2 A and AA) on 12 pages at 1440, 768 and 390px in English: no
  serious or critical violations outside Clerk's own widget.
- No horizontal overflow on any of those pages at any of those widths, in
  English or Sinhala.
- Drawer, tested in a browser: closed it is `inert`; opening moves focus in; Tab
  stays inside; Escape closes and returns focus to the menu button.
- Production guards: `AUTH_BYPASS=true` is ignored by a production build
  (checked against a running `next start`); `/kitchen-sink` answers 404 in
  production (unit test).

## Skipped, and why

- **Playwright e2e suite not run.** It needs the full servers. I updated
  `design-audit.spec.ts` for the new ring colour and shadow rules, but did not
  execute it or the other e2e specs. Run them in CI before merging.
- **First-run dashboard screenshot.** That state only appears with a live API
  (the offline demo always has a matter). It is covered by unit tests and I
  looked at it once on a throwaway page, since deleted.
- **"Open a sample matter"** on the first-run panel: skipped, as the brief says,
  because there is no sample data in a live workspace.
- **Workflow picker dialog** for "Create a matter": not built. The header
  button and the workflow cards all open `/new`, the existing flow, so there is
  already one way in.
- **Icon rail** for 768 to 1023px: I used the drawer for everything below
  1024px instead.
- **Billing** has no skeleton: it has no list, and its one async part (the
  pilot dates) falls back quietly, which an existing test requires.
- **Loading skeletons and API error states** are covered by tests, not by
  screenshots: the offline demo cannot trigger them.
- **Workspace screens outside the six pages** (documents, facts, checks,
  drafts, exports, approvals, the new-matter wizard) got the global tokens and
  component changes but no layout work. Several still have two to four gold
  `primary` buttons in one view (exports 4, checks 4, approval 3, new matter 3).
  The one-gold rule is applied to the dashboard, sign-in, sign-up, Matters,
  Research, Legal sources, History, Billing, Settings and Profile.
- **Aceternity** components were not touched.

## Data the UI wants but does not have

Every slot renders cleanly without these.

- A per-matter **next action**. The dashboard derives "Review" or "Open" from
  the state.
- A matter **display name and property description**. The list shows the client
  reference and the reference number.
- **Real obligations.** The dashboard's upcoming obligations come from demo
  fixtures only; with the API on, the section always says "Nothing due".
- A **matter count total and paging**. The feed fetches the first 50 matters
  (`useRecentMatters(50)`) and ignores `nextCursor`, so counts and the Matters
  list agree with each other but are both capped at 50.

## Open questions

1. Paging for practices with more than 50 matters: add "Load more" using the
   existing cursor, or a server-side count?
2. Where do obligations come from in production?
3. Should the one-gold-button rule be applied to the workspace screens listed
   above in a follow-up PR?
4. `docs/plan.md` still describes the teal focus ring and the earlier radius
   spec. `CLAUDE.md` was updated in this branch; should `docs/plan.md` follow?
5. The nav labels "Matters" and "History", and "Research" and "Legal sources",
   may confuse users. I did not rename them.
6. The Sinhala UI is switched off in the product (commit `eda85bc`). Do you want
   it back on, and who reviews the Sinhala?

## Separate issues found, not fixed here

- **Sinhala hydration error.** With the Sinhala locale on, the dashboard logs a
  hydration mismatch and the Next dev badge shows "1 Issue". It is in the
  "before" screenshots, so it predates this work. It comes from the disabled
  Sinhala path. To be fixed in its own branch.
- **Sinhala catalogue is mostly English.** `si.json` has few translations; most
  strings fall back to English.
- **Native email validation** on sign-in is the browser's own bubble, left as is
  by decision.
- Settings checkboxes are 16px; their label row is the 44px target.

## Reviewer notes

- **History search and filter** logic changed in one file:
  `frontend/src/components/activity/history-screen.tsx`. Also
  `activity-timeline.tsx` (empty state only) and `activity-screen.tsx` (one
  class).
- **Matters filters** live in `matters-screen.tsx` and
  `frontend/src/lib/home/practice-snapshot.ts`; the dashboard counts and the
  list use the same predicates, with a test that each count equals its list.
- **CLAUDE.md** was edited to record the navy and gold focus ring and the
  radius as built.
- The unused `GavelAnimation` component was removed (it stays in git history).
