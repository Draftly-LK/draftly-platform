# UI refresh — "Trust & authority" (test branch)

A visual refresh of the workspace for evaluation. It changes presentation only;
no backend, API contract, data model, or legal wording is touched.

## Design direction

Generated with the ui-ux-pro-max design-system tool for "legal practice
management professional workspace" (variance 4, motion 3, density 7):

- Pattern: trust & authority; style: accessible & ethical.
- Palette: authority navy with a restrained gold accent. Gold marks the one
  primary action and the current place, never status. Status hues (teal,
  amber, red) are unchanged.
- Type: a legal-register display serif (Source Serif 4, with Noto Serif
  Sinhala) for page titles and the wordmark; IBM Plex Sans with Noto Sans
  Sinhala stays for UI and body text.
- Motion: subtle (one 320 ms rise-in on the home hero, and 150 ms colour
  transitions); `prefers-reduced-motion` still disables it.

## What changed

- Tokens (`src/styles/globals.css`): cooler canvas, deeper ink, new
  `navy-950/900/800`, `gold`, `gold-strong`, `gold-soft`, and two elevation
  tokens (`shadow-card`, `shadow-raised`). Cards use a 10 px radius.
- Navigation rail: navy, white wordmark, gold "Create matter", gold marker on
  the current page.
- Page header: serif title, optional eyebrow; inside a matter it steps down a
  level and drops its duplicate language control.
- Home: navy hero with greeting, two primary actions, and a "practice at a
  glance" panel counted from the same matter feed as "Recent matters" (API or
  demo). Quick actions, recent matters beside upcoming obligations, and common
  workflows as cards.
- Matter header: record-style header with the reference in the serif and a
  gold active tab.
- Panels across screens: the shared card treatment.
- Checks (demo): findings show their text and a status badge instead of raw
  ids.

## Fixes found while auditing

- `useTokenProvider` called Clerk's `useAuth` even with no `ClerkProvider`
  mounted, so `/library` and `/research` crashed in the offline demo and local
  development. It now picks a no-token provider when no publishable key is set.
- The gold "in this release" tag failed 4.5:1 contrast; `gold-strong` is
  darker.

## Checks run

- Playwright sweep of 20 routes at 1440, 1024 and 390: no console errors, no
  horizontal overflow, no serious or critical axe violations.
- `tests/e2e/design-audit.spec.ts` updated to the new tokens, the named
  elevation tokens, and the display serif for page titles.

## Human gates

- `docs/plan.md` §Design system still specifies the previous tokens and "no
  card shadows". This branch departs from it for evaluation; if the refresh is
  kept, the plan should be updated by the team.
