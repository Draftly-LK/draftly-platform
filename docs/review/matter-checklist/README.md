# Matter checklist review — 2026-10-09

All records and screenshots in this directory are synthetic. The implementation
follows the [approved design](../../superpowers/specs/2026-10-09-matter-checklist-design.md)
and [implementation plan](../../superpowers/plans/2026-10-09-matter-checklist.md).

## Implemented journey

Matter Overview leads with recorded completion, assessment uncertainty and one
next action. Six groups cover documents/facts, evidence/checks, drafting,
signing/attestation, stamping/registration and final completion. Rows show state,
reason, supporting records and an action; details retain attribution and history.
Completed and inactive rows remain accessible below outstanding work.

Document processing queues source-bound review proposals through the existing
outbox. The agent can also propose a fact-triggered operational task through its
existing tool allowlist. A lawyer accepts or dismisses proposals, adds tasks,
links support and records conclusions. Unaccepted proposals do not count toward
completion. Source-file, document, interpretation-generation, fact and association
changes invalidate affected decisions without deleting their history.

Checks reuses the Subjects and transactions editor directly. Roles and parcel
associations are explicit and versioned. Requirements expose Collection, Evidence
review, Physical-original inspection, Currency and Consistency independently.
Original inspection being unnecessary does not make the requirement unnecessary.
Issue gates use neutral language and explain their limited meaning. Historical
passes with changed inputs need review, and failed reads do not imply clean checks.
Shell evidence progress follows actual requirement satisfaction, never the matter
stage alone. A missing checklist assessment has a direct setup action.

## Preservation and integration

Work began in an isolated worktree on `dev/codex/matter-checklist`, leaving the
original workspace's uncommitted work intact. PRs #102 and #103 were already
merged. The branch retains their CI repairs, global 75% branch floor and bundled
fonts. Frameworks, dependency locks, legal text and legal policy are unchanged.

During implementation main advanced to `54ea162`, including PRs #106 and #108.
The feature was rebased onto that revision. Requirement-selection guidance and
the Drafts → Verified facts transaction setup hash/focus behavior were preserved.
The two requirement-panel conflicts received a fresh independent integration
review; its focused four-file suite passed 49 tests.

## Independent review and resolutions

Backend and frontend reviewers worked separately from implementation. Important
findings were verified against the code and resolved with regression coverage:

| Finding | Resolution |
| --- | --- |
| Completion could discard existing source dependencies | Existing support is preselected; the server refuses dependency removal during completion. |
| Renewed review retained obsolete pins or ignored selected replacement support | Untouched support adopts current owner versions; explicit replacement selections are sent. Prior pins remain in history. |
| Delayed history/evidence responses could overwrite current UI state | Separate request epochs reject obsolete responses. |
| Multiple template families in one scope could hide unfinished drafting work | Projection identity includes template and explicit transaction/party/parcel scope. |
| Non-applicable requirements with stale links could inflate outstanding work | Applicability exclusion takes precedence. |
| Available source metadata could hide absent/corrupt original bytes | The document owner validates current original integrity. |
| Processing reruns omitted reused document interpretations | Events and proposals carry eligible document versions and interpretation generations, including reused grouping. |
| Duplicate proposals ignored document-generation changes | Deduplication includes exact document pins. |
| Approval sorted before draft preparation | Drafting work precedes approval; row order and next action are tested. |
| Empty assessment exposed a technical missing-snapshot error | The specific backend state shows assessment guidance and a direct shared setup-editor action. |

No important independent-review findings remain open. The final ordering review
passed six projection regressions. Legal wording and final visual approval remain
human PR review responsibilities.

## Behavior verification

The browser used actual Next.js components and actual FastAPI services against
disposable local PostgreSQL 18. A separate, temporary frontend copy supplied a
synthetic token; the temporary test-only server used the existing seed identity
adapter. Production authentication code was unchanged. No live credentials,
client records or external model-provider calls were used.

The acceptance journey exercised task creation, linking a synthetic source,
completion with a lawyer note, refresh persistence and historical evidence pins;
two party subjects and a parcel; explicit roles and transaction selection;
automated checks with missing facts; keyboard activation; Sinhala rendering;
1024px layout and doubled text without horizontal overflow. Missing facts yielded
Inconclusive and non-applicable checks rather than an overall pass.

Five focused axe scans of existing/empty Overview, existing/empty Checks and
Sinhala Overview found no violations, and the final acceptance run reported no
browser page errors. Empty assessment guidance opens and focuses the existing
transaction editor; no transaction shows Not run. Results are recorded in
[browser-results.json](browser-results.json). Screenshots show synthetic states,
not legal sign-off or deployment evidence.

Backend regressions exercise owner isolation, live capability checks, replay,
versions, explicit associations, duplicate proposals, completion history, changed
originals and interpretations, manual decisions and an actual processing HTTP
request → outbox dispatch → proposal → acceptance → completion → invalidation.
Frontend tests cover failed requests, exact retries, obsolete responses, evidence
selection and refresh. The additive migration was exercised on disposable schemas.

## Verification gates

- Backend lock check, Ruff, format and mypy passed; mypy checked 400 source files.
- Required backend unit/contract/conformance gate: **1,158 passed, 3 expected failures**.
- Follow-through and bootstrap regression run: **42 passed**, including real database processing.
- Final frontend typecheck, lint and production build passed after integration.
- Full frontend coverage run: **874 tests passed across 92 files**, with **83.99% branches**, 71.75% lines/statements and 79.31% functions. All configured global and library floors passed.
- Markdown and diff checks passed before the evidence commit.
- The global 75% branch floor and the stricter library coverage floors remain intact.

The broad backend run returned 2,994 passed, 34 failed, 6 skipped and 5 expected
failures. One feature registry expectation was corrected and its focused suite
passed. Every remaining failing node reproduced independently on untouched base
`77f94c4`, whose backend is identical to the latest main baseline. The whole
upstream suite was not rerun; each remaining failure was reproduced directly.

| Existing failing test file | Count |
| --- | ---: |
| `document/tests/test_ingestion_service.py` | 15 |
| `document/tests/test_vision_adapter.py` | 1 |
| `document/tests/test_processing_status.py` | 1 |
| `matter_agent/tests/test_task6_research.py` | 9 |
| `matter_agent/tests/test_task6_contracts.py` | 1 |
| `matter_agent/tests/test_turn_runner.py` | 1 |
| `matter_agent/tests/test_agent_service.py` | 2 |
| `tests/db/test_ingestion_replay.py` | 1 |
| `tests/integration/test_matter_agent_neon_e2e.py` | 2 |
| **Total** | **33** |

Paired comparisons used each checkout's backend and PYTHONPATH, the uv-managed
Python 3.12 environment, seed 0 and the full-run seed 97710297. Seven module files
returned the same 30 failing node IDs and 74 passes on both checkouts. Existing
ingestion replay/migration runs returned the same one failure, 16 passes and one
expected failure. The three remaining database/integration nodes also failed on
base. No test assertions or repository gates were weakened.

## Practical limits

The later-phase rows record operational work. They do not create an attestation,
submit to a registry, calculate a statutory obligation or legally close a matter.
Existing owner services still control those records, approval and export.

The existing readiness policy does not establish complete automated-check
coverage, so the checklist retains its assessment notice where appropriate.
Agent proposals use the existing configured agent path; processing follow-through
does not require a new model provider. This change does not add new legal task
definitions or infer ambiguous party roles. Deploy the additive backend support
before the frontend. Human merging, deployment and legal/visual approval remain
outside this verification run.
