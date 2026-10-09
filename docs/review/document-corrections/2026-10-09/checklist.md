# Task 4 synthetic document-correction review

This packet contains synthetic evidence only. Captures are review artifacts,
not approved visual baselines. Human visual identity and Sinhala terminology
approval remains pending.

## Scope and method

The ignored Playwright/esbuild harness mounts the actual document review,
decisions, canonical register, inbox and recovery components against synthetic
HTTP responses. Clerk/token/Next navigation adapters are harness-only.
Production authentication was unchanged; the actual unconfigured protected
route still redirects to the Clerk configuration screen. Existing Next styles
and font assets come from this worktree's development server on port 4312;
4310 belonged to another workspace and was preserved.

Fourteen final captures cover both English and Sinhala: correction required at
1440 by 900; failed refresh/history, successful refresh/history, unclaimed-page
recovery, recovered group and unsupported manual status at 1024 by 768; and
unsupported manual status at 200% text size in both locales. The source viewer
and canonical register remain shared. Values explicitly marked synthetic stay
historical after successful refresh until a new lawyer review.

After final lint removed obsolete noninteractive table focus stops, a separate
four-state check against the final production assets repeated the inbox at
100/200% text in both locales. It again records zero console/asset errors,
root/internal overflow and Axe serious/critical findings in
`synthetic-final-inbox-measurements.json`.

The harness records generation 3 after correction, two separate refresh attempts,
and unchanged stale flags on the old fact/review in both locales. The first
attempt has a typed failed outcome; the second succeeds. This verifies UI
consumption of those outcomes, not the provider or persistence implementation.
Separate ASGI/PostgreSQL tests prove committed replay counts and authorization.

## Mechanical results

| Check | Result and evidence |
| --- | --- |
| Console and assets | PASS for final mounted synthetic paths: zero console errors, warnings, page errors or failed requests in `synthetic-measurements.json` |
| Root, table and pane overflow | PASS: zero in all 14 final states, including both 200% text captures; final probe also includes summary labels |
| Axe | PASS: zero serious/critical violations in all 14 states |
| Focus | PASS for changed native controls: recorded keyboard focus is visible with a 2px outline; compact rows remove the horizontal table scroll requirement. Full authenticated keyboard-only workflow remains a Task 8 integration gate |
| Reduced motion | PASS: reduced-motion preference enabled; primary transition `1e-05s` |
| Font loading | PASS: loaded Plex and Source Serif in English; loaded Noto Sans Sinhala and Noto Serif Sinhala with actual glyph/weight probes in Sinhala |
| Routes and link destinations | PARTIAL: mounted component API routes exercised; protected real routes and all navigation destinations require configured authentication in Task 8 |
| EN/SI controls | PASS for changed grouping, history, extraction, evidence renewal, recovery and inbox generic controls; governed document-type labels still use the existing taxonomy and need owner terminology review |
| Lighthouse | PASS threshold: accessibility 100, best practices 96 on the script-free synthetic rendered review snapshot; not an authenticated runtime or performance claim |

Lighthouse 13.5.0 emitted its Node engine advisory (requires 22.19; repository
runtime 22.16). The static snapshot cannot recreate the live blob source-image
URL and records a console asset error. The existing shell search shortcut has
the visible-label/name advisory. The live mounted browser path loads the image
and has zero console/asset errors; the two kinds of evidence are distinct.
The raw Lighthouse JSON retains these limits rather than hiding them.

## Token and screenshot critique

PASS: existing canvas is computed `rgb(243, 245, 248)`; existing navy shell,
cream primary actions, outlined controls and configured fonts are preserved.
Statuses use icons and text. No new decorative surface or legal copy was added.
Historical status is displayed with a separate visible stale-evidence warning.

The document page remains legible beside correction controls at 1440 and above
them at 1024. Page source, range and order controls stay together. History shows
the original three-page ranges and subsequent one-page correction. Narrow inbox
rows use labelled cells; the source filename and review action remain readable.
At doubled text size, the summary grows vertically instead of overlapping its
counts. The full-page captures contain the existing fixed sidebar at the scroll
position used by the browser; that is not a new sidebar layout.

No remaining screenshot blocker was identified after the bounded repair.
This is AI critique only. It does not approve visual identity, terminology,
statutory wording or a visual regression baseline.

## Iterations and human gate

See [issues.md](issues.md) for fixture mistakes, actual defects and their tests.
Three inbox visual iterations exposed a remaining summary-label collision.
The controller explicitly permitted one narrowly diagnosed functional repair
beyond the cap: replace the fixed five-column summary with font-relative
auto-fit columns. No general redesign was authorized. Final captures and probes
pass after that repair; the cap exception does not grant human visual approval.

Pending owner/integration gates:

- Human review of these concrete captures and Sinhala generic terminology.
- Configured-authentication route/link and full keyboard-only journey in Task 8.
- Required bounded provider deadlines and cancellation-safe persisted failure
  recovery in Task 8; Task 4 only handles calls that return or raise.
- Task 5's empty pre-checklist intake class/schema context dependency.
- Existing governed legal taxonomy and template wording remain human-owned.
- Independent review must resolve the no-logical-extraction fallback: a newly
  created unsupported group opens original previews and document decisions in
  `ClassificationReviewScreen`, which has no shared canonical manual register.
  The processing-review branch and backend current manual generation contract
  are tested; this fallback was not claimed as covered by these captures.

The review servers on ports 4312/4314 were stopped after capture. Intermediate
harness scripts, native red/green logs and detailed implementation report remain
under `.superpowers/sdd/2026-10-09-lawyer-led-matter-workflow/`.
