# Checklist tab review

## Scope

The matter checklist now has its own tab, immediately after Overview, at
`/matters/[id]/checklist`. Overview displays the existing matter assistant.
The checklist uses the existing component and API, retaining tasks, evidence,
completion records, progress and history. English and Sinhala labels are included.

This is a focused follow-up to PR #110. It does not change backend policy,
statutory wording, approval/export eligibility or the 75% global branch floor.

## Verification

| Check | Result | Evidence |
| --- | --- | --- |
| Dedicated route and active tab | PASS | `browser-results.json`, `checklist-1440.png` |
| Checklist removed from Overview | PASS | `overview-1440.png`, dashboard regression test |
| Existing checklist actions remain available | PASS | Real checklist rendered against the synthetic backend; Add task enabled |
| Keyboard navigation and refresh | PASS | `browser-results.json` |
| English at 1440 and 1024 pixels | PASS | `checklist-1440.png`, `checklist-1024.png` |
| Sinhala at 1024 pixels | PASS | `checklist-si-1024.png`; no document overflow |
| Accessibility | PASS | Zero axe violations in both locale scans |
| Browser runtime errors | PASS | Zero page errors in the acceptance journey |
| Navigation/screen/checklist regressions | PASS | 19 tests across four files |
| Independent tab review | PASS | No important findings; route, locale, offline state and data reuse reviewed |

All screenshot content is synthetic. The existing isolated browser fixture used
port 4317 and a test-only seed identity. Production authentication was unchanged.

## Visual review

The existing shared tab bar, page header, spacing, colors and checklist component
are reused. The screenshots show a clear Checklist heading and the checklist's
progress, next action, grouped tasks and collapsed completed/history section.
Overview's assistant remains visible. No visual blocker was found in the changed
layout. Human visual acceptance remains with the PR reviewer.

## Known limitation

These checks verify the moved checklist with synthetic data. They do not establish
the practising status or permissions of the account in the user's screenshot.
