# Pass 3 - Accessibility and keyboard

## Sweep

All 18 inventory routes were scanned with `@axe-core/playwright` at
1024 x 768 under reduced motion. The interactive walkthrough covered the
palette trigger and native `Ctrl+K`, `Escape`, focus return and visible focus,
keyboard-only fact correction, modal autofocus/dismissal, and a 512 px reflow
proxy for 200% zoom on Facts, Draft editor, and Assistant.

## Findings and fixes

| Finding                                                                                                        | Severity | Fix                                                                                                                                  | Result                                                                                                                  |
| -------------------------------------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| Opening the command palette crashed because `cmdk` inputs and lists had no `<Command>` provider.               | Critical | Wrapped the command surface in the required provider and added console-error assertions around both pointer and keyboard activation. | PASS: pointer activation and native `Ctrl+K` open the palette with no console error; `Escape` closes and returns focus. |
| Correction and check-resolution dialogs did not consistently place focus or support direct `Escape` dismissal. | High     | Added deterministic autofocus and keyboard dismissal to each custom dialog.                                                          | PASS: keyboard-only correction reaches the input, and all reviewed dialogs dismiss without trapping focus.              |
| Status treatment needed an explicit semantic audit target.                                                     | Medium   | Added `data-status` to the shared badge and asserted every icon-bearing status also contains text.                                   | PASS: no audited status relies on color alone.                                                                          |

## Result

PASS. Axe reported zero serious or critical violations on every route. Focus
is visible, the demo path is keyboard-operable, reduced-motion overrides are
applied, and the 200% reflow proxy has no horizontal page overflow.
