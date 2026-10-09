# Task 4 review issue log

All fixtures are synthetic. This records failures separately from final passing
captures; no human-approved baseline was created.

| Finding | Cause and change | Evidence/result |
| --- | --- | --- |
| Harness did not render decisions | Fixture matched `/inbox` instead of actual `/document-inbox`, producing the wrong response shape | Corrected ignored fixture route; no production guard weakened |
| Harness recovery shape crashed | Fixture used `overlapPageNumbers` rather than wire `overlappingPageNumbers` | Corrected ignored fixture; actual typed API contract unchanged |
| Harness page-status selector timed out | Exact label matcher included the select's option text | Used the combobox accessible name; component behavior unchanged |
| Stale facts looked current in the closed register row | Historical review status remained visible without the evidence warning until opening review | Native `task-4-red-stale-list.log` failed; visible warning/icon added; `task-4-green-stale-list.log` has 27 passing canonical tests |
| Source table failed Axe keyboard-scroll check | Horizontal table wrapper was not focusable | Initial focus workaround was superseded by compact rows eliminating horizontal overflow. Final lint rejected noninteractive wrapper tabIndex; removed the now-unneeded focus stop. No lint exemption was added |
| Confirmed group could not be reopened from inbox | Review action depended only on classification/boundary flags | Review link remains available; extraction freshness is visible; exact page range lengths replace fragment-count display. `task-4-red-inbox-correction.log` failed; final owning selection has 56 passing tests |
| Narrow table cells collided at 200% text | Fixed desktop table columns had insufficient text room | Labelled compact rows at 1024; desktop table remains at wide breakpoint; final cell/pane probes and screenshot critique clear |
| Sinhala summary labels collided and overflowed | `lg:grid-cols-5` forced five narrow cells at doubled text size; an attempted auto-fit string replacement did not match the formatter's class order, so it never applied | Preserved `task-4-browser-red-si-zoom.log`. Controller allowed one exact cap exception; applied font-relative auto-fit directly. Final 14 probes include summary labels and all pass |
| Generic owning Sinhala labels remained English | Existing inbox/count/source-state entries had not been translated | Completed changed generic entries and source/boundary statuses; locale structure/ICU tests pass. Governed document taxonomy remains an owner gate |

Visual iterations: document correction/review had two iterations (visible stale
rows and final bilingual inspection); inbox/recovery had three, followed by the
explicitly permitted summary-only functional repair. Harness fixture/selector
corrections are recorded as tooling errors, not additional design iterations.
Earlier fixture runs printed their native failures in tool output and reused
the working browser log; the representative Sinhala zoom failure has its own
retained native log. Final passing run is `task-4-browser-final.log`, with
sanitized measurements in this directory.

The fixed summary uses existing grid/control/surface tokens. At 200% it becomes
vertical, retaining all labels/counts without root or internal overflow. Human
visual identity and Sinhala terminology acceptance remain pending even though
the mechanical repair passes.
