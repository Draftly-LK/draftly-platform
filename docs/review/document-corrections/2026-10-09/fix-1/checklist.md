# Task 4 focused review fixes

This packet covers independent-review findings R1–R4 and the related manual
original fallback (M1), from source base `404ac5a`. All fixtures and captured
values are synthetic. Human visual identity and Sinhala terminology approval
remains pending; these captures are review evidence, not approved baselines.

## Functional changes

- Edited classification, grouping and page-status commands retain the snapshot
  the lawyer reviewed. Changed or missing originals, page accounting, member
  documents and selected retirement versions require deliberate renewal.
  Renewal clears previous retirement choices and reasons. Ambiguous replay keeps
  the original key and precondition; an acknowledged command followed by a failed
  current read does not offer another creation command.
- The actual no-logical-extraction route now uses the shared canonical register
  with the current document generation. Unsupported and failed first extraction
  outcomes retain manual entry and readable originals. A first successful
  refresh changes to the processed-page viewer without reloading the route.
- Processed pages show their current or historical interpretation and original
  filename/reference with original page number. Two originals containing page 1
  remain distinguishable. Historical views expose the current fragment originals.
- Manual references without an extraction run offer the original file instead
  of an unavailable processed-page action. This is page provenance, not fabricated
  text or bounding-box precision.
- The generated OpenAPI artifact includes the five missing document/recovery
  routes and generation, extraction, page-accounting and history contracts.
  Existing custom missing-header errors remain unchanged.

## Verification scope

The browser harness mounts actual production components/API clients with
synthetic HTTP, token and Next-navigation adapters. Production CSS and local
font assets come from the worktree's Next server on port 4312. The earlier
inbox visual-iteration cap is unchanged; this is functional review work.

The focused owning component suite passes 71 tests across eight files.
Contract/header gates pass 90 tests with one existing expected failure and one
existing Starlette/httpx warning. Six migrated PostgreSQL ingestion replay/auth
tests pass, with the existing Alembic configuration warning. No broad backend
suite was repeated, no known drift exemption changed, and no database migration
or backend runtime implementation changed in this fix round.

All twelve final browser probes pass: English and Sinhala historical attribution
at 1440 and 1024/200%, no-logical manual entry at 1440, original fallback and
412 renewal at 1024/200%, and successful first refresh at 1024. There are zero
root or pane overflows, zero Axe serious/critical findings, and zero unexpected
console/page/asset errors. The eight expected review-404 and two expected
boundary-412 native HTTP console diagnostics remain in the measurements,
classified by exact synthetic route/status. They exercise required fallback
and stale-version behavior and are not suppressed.

The manual submission preserves original B, original page 1, document ID and
generation 2. The two original-page-1 controls select distinct processing page
IDs. Explicit renewal replaces the old grouping and moves focus to the current
class selector; component regressions separately verify group/page focus and
same-source-version membership changes. These are functional checks, with no
new visual-design iteration.

The initial browser failures were diagnosed harness errors: an exact select
label query that included option text in Chromium, a fixture variable shadow,
and the invalid fixture origin `manual` (the contract uses `lawyer`). Their
native logs and diagnostic measurements are retained in the ignored SDD
workspace. The final captures use the corrected contract fixture.

Final quality-gate results are recorded in the Task 4 report. This UI fixture
exercise does not prove provider
completion, canonical accuracy, legal sufficiency or a real authenticated full
workflow. Task 5's intake catalogue dependency, Task 6's existing agent index
drift, and Task 8's provider bounds and integrated accessibility/runtime work
remain explicit dependencies.
