# Pass 2 — Spec fidelity

## Sweep

The route inventory was checked against the interface specification, followed
by a stateful end-to-end run: create matter, synthetic upload processing,
fact verification and conflict resolution, workflow decision, check
resolution, scoped assistant actions, verified-fact draft generation,
FactChip rendering, version save/compare, approval/export, and live activity.

## Findings and fixes

| Finding                                                                                          | Severity | Fix                                                                                                                                                                               | Result                                                                                              |
| ------------------------------------------------------------------------------------------------ | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| A newly created matter stopped after upload because it had no deterministic review/check record. | High     | Initialize each new matter with isolated clones of the synthetic fact and check fixtures; make draft eligibility use fact keys; route workflow audit events to the active matter. | PASS: the complete demo runs on `matter-rta-002`.                                                   |
| Assistant and draft lifecycle audit events were hard-wired to the seeded matter.                 | High     | Route assistant actions to the current matter and infer matter ownership for version, approval, and export events.                                                                | PASS: the new matter Activity view records the full live session.                                   |
| React omitted the boolean `data-fact-chip` DOM attribute.                                        | Medium   | Emit an explicit empty data attribute.                                                                                                                                            | PASS: generated verified/corrected facts render as inspectable FactChips and print selectors apply. |
| Saving a new draft version left the previous version selected and approval disabled.             | High     | Synchronize editor selection to the newly active version after save.                                                                                                              | PASS: save → compare → approve → export completes without interruption.                             |

## Result

PASS. Every listed region and governed state was asserted, including document
failure recovery and replacement history, all five fact states, conflict
candidates, blocked override, grounded/insufficient assistant outcomes, draft
generation gate, version restore controls, and live audit history.
