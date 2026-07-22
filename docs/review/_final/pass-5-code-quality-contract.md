# Pass 5 - Code quality and contract integrity

## Sweep

The complete type directory was compared with the plan's core and additional
types. Store actions, async accessors, API swap markers, audit emission,
matter ownership, render determinism, interface copy, dependencies, token
vocabulary, and route console output were inspected. The optimized production
build then ran the complete Playwright suite.

## Findings and fixes

| Finding                                                                                                                        | Severity | Fix                                                                                                                                                    | Result                                                                                                |
| ------------------------------------------------------------------------------------------------------------------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| Upload, retry, and manual-fact paths could attribute mutations to the seeded matter while operating on a newly created matter. | Critical | Pass active matter ownership into uploads/manual facts and infer retry ownership from the document.                                                    | PASS: the isolated `matter-rta-002` demo records its complete activity without seeded-matter leakage. |
| `Obligation.matterId` was optional although the authoritative additional-type shape requires it.                               | High     | Made the field required and assigned the deterministic demo matter to every fixture.                                                                   | PASS: the contract matches the plan and typecheck is green.                                           |
| Metadata and replacement-history copy bypassed next-intl.                                                                      | Medium   | Added catalogue keys and locale-aware metadata generation.                                                                                             | PASS: static JSX/attribute scans find no hardcoded interface copy.                                    |
| Four installed Radix/CVA packages had no implementation use.                                                                   | Medium   | Removed the unused packages and lockfile entries; retained `motion` through the allowlisted, reduced-motion-aware first-run fade required by the plan. | PASS: declared runtime dependencies are used or framework-mandated.                                   |
| Activity used runtime-specific localized date formatting, producing a Node/Chromium Sinhala hydration mismatch.                | High     | Generate a deterministic Colombo date/time value and localize its surrounding label through next-intl.                                                 | PASS: zero console errors or warnings across the production route sweep.                              |

## Result

PASS. `pnpm typecheck`, `pnpm lint`, `pnpm test`, and `pnpm build` are green.
All 12 production Playwright tests pass, including the 18-route console,
design, axe, responsive, spec-fidelity, and complete demo-path checks. Every
accessor/action has a `TODO(api)` marker, every mutation emits an `AuditEvent`,
and scans find no `Date.now()` or `Math.random()` render usage.
