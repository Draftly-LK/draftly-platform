# Pass 4 - Responsive and i18n

## Sweep

All 18 routes were checked at 1024 x 768 for page overflow and desktop rail
state. Home, New matter, Matters, Documents, Facts, Draft editor, and
Assistant were repeated at 767 px to verify the breakpoint. The complete demo
path was traversed under the Sinhala scaffold, switched back to English, and
representative workspaces were stress-tested with labels expanded by 30%.

## Findings and fixes

| Finding                                                                                                       | Severity      | Fix                                                                                                              | Result                                                                                               |
| ------------------------------------------------------------------------------------------------------------- | ------------- | ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Matter-level routes did not expose the EN/Sinhala control, interrupting locale switching along the demo path. | High          | Added the shared locale control to the matter header beside the actions menu.                                    | PASS: locale control is present on Documents, Facts, Workflow, Checks, Drafts, editor, and Activity. |
| Activity displayed internal action and target identifiers such as `fact.corrected`.                           | High          | Added complete next-intl action and target catalogues with a localized unknown-event fallback.                   | PASS: no raw translation or audit identifiers appear in the audited demo path.                       |
| The first-run `/new` screen intentionally has no application rail.                                            | Informational | Corrected the audit to validate its standalone first-run layout while retaining rail assertions everywhere else. | PASS: the first-run layout and all app-shell routes match their specified responsive structures.     |

## Result

PASS. Every route has zero page-level horizontal overflow at 1024, rails
collapse below 768, Sinhala glyphs fit their controls with the Noto Sinhala
font stacks applied, EN-to-Sinhala-to-EN switching succeeds, and 30% longer
labels do not break the representative layouts.
