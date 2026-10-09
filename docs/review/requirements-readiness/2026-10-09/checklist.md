# Requirements and readiness review

Synthetic component-contract browser packet, 2026-10-09. Human identity and legal
terminology approval remains pending with the controller for the integrated review.

- [x] Real Checks, Documents and Overview components rendered with current production
  Next CSS and bundled IBM Plex Sans, Noto Sans Sinhala and Source Serif 4 fonts.
- [x] English and Sinhala: 1440 and 1024 CSS-pixel widths, screenshots and ARIA trees.
- [x] Checks at 200% text size in both languages; no page horizontal overflow.
- [x] Fourteen third-pass probes completed their strict overflow and axe checks;
  no serious or critical axe violations. Each saved a screenshot and ARIA tree.
- [x] Unknown-readiness behavior tail saved an additional screenshot/ARIA probe.
- [x] Keyboard focus is visible with a 2px outline. Filter controls have linked labels.
- [x] Manual original inspection retries a synthetic 503 with the same request key,
  exact body and displayed If-Match version, then shows the saved state.
- [x] Run checks sends the explicitly selected transaction, subject and association
  revision. No default first subject selection.
- [x] Manual original work and governed requirement review are separate from
  automated results; history/source references remain visible.
- [x] Overview renders unavailable readiness as unknown with refresh, not zero blockers.
- [x] Production Next routes in routes.json returned HTTP 200; this tests route
  existence, not authenticated end-to-end behavior.
- [ ] Controller human identity/terminology approval, including inherited English
  legal catalogue labels within the Sinhala interface.
- [ ] Integrated real-API latency and authenticated journey: controller Task 8.

The browser fixtures provide synthetic HTTP responses and replace auth/Next adapters
inside the harness. They do not prove real evidence-read performance or provider
behavior. Production build/typecheck, migrated database tests and API contract tests
provide separate evidence; see the Task 5 report.

The third-pass script completed all fourteen mechanical probes, then its behavior
locator failed before the JSON writer. Screenshots and ARIA files were already saved.
The unchanged-product tail used an action-role locator, completed the retry/scope/
unknown/focus probes and wrote browser.json. The controller accepted this as a harness
repair, not a fourth visual design iteration. The first fourteen per-probe numeric
objects were not recovered; their strict assertions and file outputs are retained.
