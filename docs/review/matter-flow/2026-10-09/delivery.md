# Lawyer-led matter workflow delivery evidence

Feature branch: `dev/codex/lawyer-led-matter-workflow`.
[PR #98](https://github.com/Draftly-LK/draftly-platform/pull/98) was human-merged
at 08:34:11 UTC on 2026-10-09 through `cc7c07e`. Remaining source/date changes,
final fixes and delivery evidence belong to draft
[PR #100](https://github.com/Draftly-LK/draftly-platform/pull/100).
This report distinguishes implemented behavior, retained verification, and
acceptance that remains unverified. It is not a claim that every success
criterion passed. A human merges the PR.

## Delivered behavior

Uploaded sources retain processing attempts, failures and recovery actions.
Document classification/grouping corrections preserve originals, retire affected
interpretations, and invalidate dependent facts and results. Provider and
application deadlines bound processing; expired attempts have an authorized
recovery command. Processing remains synchronous, without an autonomous reaper.

The matter owns a form-free fact register. Immutable candidate values and source
pages/text remain available beside lawyer decisions, corrections and history.
Party, parcel and transaction associations are explicit. Missing or ambiguous
roles cannot silently become form bindings. Manual input records provenance and
verification state; only eligible reviewed facts feed approved outputs.

Overview and the full Assistant share persisted conversation. Implemented tools
use authorized owning commands, exact-version confirmation, audit and replay
contracts. Checklist receipt, evidence sufficiency and human review remain
separate. Missing requirements are visible in Documents; readiness and next
actions use backend state, including unknown coverage.

Optional Form 8 preparation selects an explicit transaction, parcel and parties.
The draft exposes missing/conflicting particulars and preserves exact reviewed
fact bindings. Changes invalidate dependent review, snapshots and export.
Populated fields do not establish legal approval or registration readiness.

The approved statute extension adds signed audience-specific source releases,
original/index checksums, official source metadata and amendment relationships.
The existing controlled engine is reused through a pinned boundary. Source
quotations need independent approval and signed exact excerpt descriptors;
missing release artifacts or policy cannot fall back to unrestricted retrieval.
Real-source publication, signing custody and content review remain owner gates.

Conversation source inspection records both the server business date and the
selected transaction's eligible reviewed attestation date, with exact fact and
association versions. Missing/conflicting dates lead to lawyer input. Typed
source/date context survives unsupported answers and refresh. Current policy
projects historical legal answers conservatively for both UI and model history,
while preserving immutable stored rows, hashes and audit references. Unknown or
withdrawn passage availability withholds text; metadata leads stay distinct from
supporting citations. The shared EN/SI source panel shows known/unknown dates,
official links, releases and recorded relationships.

## Acceptance status

The owner explicitly selected V0 user/matter isolation and deferred organization
support. At 07:43 UTC on 2026-10-09 the owner waived further local test suites,
browser verification and benchmarks. Existing tests and thresholds were retained.
Static checks, builds and independent reviews continued. Automatic CI on pushed
commits was observed, without manual reruns. PR #98 was subsequently human-merged;
the agent neither merged nor pushed `main`. The requested one-hour target was
exceeded and reported; skipped evidence is not relabeled as passed.

| Criterion | Implemented evidence | Remaining acceptance |
| --- | --- | --- |
| Ingestion | Persistent attempts, explicit terminal state, partial recovery, deadlines and exact current-attempt settlement | Final runtime cancellation, failure/retry and mixed-bundle journey unverified |
| Extraction coverage | Four supported classes; approved 51-observation reference; five previously filtered fields now mapped | Full precision/recall/page target and robustness variants unmeasured |
| Source evidence | Source/page/text access, preserved original pins, honest text/page precision | Final integrated source navigation unverified |
| Fact review | Form-free register, accept/correct/reject, canonical decisions and immutable history | Final refreshed application journey unverified |
| Subject scope | Separate subjects, explicit roles/transactions, scoped checks and Form 8 bindings | Final two-subject integration unverified |
| Document corrections | New interpretation generations and downstream invalidation; stale authority refused | Final correction-through-draft journey unverified |
| Lawyer input | Provenance, actor/time, source references and verification state | Final missing/conflicting-input integration unverified |
| Conversation | Shared persisted Overview/Assistant, evidence-backed claims, honest provider gaps | Final refreshed conversation/source-release journey unverified |
| Assistant actions | Authorized closed tools, confirmed exact-version changes, audit and retry | Earlier scoped persistence checks passed; late integrated replay unverified |
| Checklist | Evidence links and decision currentness; governed human original inspection/review | Final editable-checklist integration unverified |
| Next action | Backend-derived pending work; unknown differs from zero blockers | Final connected navigation unverified |
| Form draft | Scoped existing Form 8; missing causes and all-binding freshness | Migration application, final runtime and human template/layout approval outstanding |
| Persistence/retry | Durable decisions/messages/drafts; opaque actor-scoped pending intents | Final concurrent/retry/refreshed journey unverified |
| Privacy/isolation | Synthetic tests and local isolation precede waiver; no client data committed | Organization deferred; late integrated isolation unverified; see handling disclosure |
| End-to-end flow | Earlier synthetic API/persistence checks and local real-case processing evidence | Complete final upload-to-draft synthetic browser/API journey not executed |
| Delivery | Atomic feature commits, independent slice reviews, original PR and static evidence | Follow-up PR and final review/check outcome recorded below before handoff |
| Added statute scope | Signed controlled retrieval, source/relationship metadata and explicit coverage gaps | Exact real-source rights/content/audience approvals and runtime coverage outstanding |

## Retained verification and limitations

Before the waiver, a broad backend run passed 2,955 tests. Later scoped assistant
receipt/auth/PostgreSQL checks passed 359 checks; frontend passed 795 tests with
84.14% branch coverage. These results precede the late Form 8, processing and
source changes; they are not final-branch acceptance.

Later reported commands passed `uv lock --check`, `uv run ruff check`,
`uv run ruff format --check`, affected `uv run mypy` paths, compile checks,
frontend `pnpm.cmd typecheck`, affected ESLint/Prettier and `pnpm.cmd build`.
Form 8 and processing/source slices produced 18-page production builds. OpenAPI
generation used in-memory synthetic settings, without a database or provider.
Exact changed Markdown checks used
`pnpm.cmd exec markdownlint-cli2 --no-globs <explicit paths>` and passed.
Exact scoped commands/results remain in the slice reports; do not infer a
whole-repository gate from an affected-file check.

The dated-conversation slice `407fb1b` passed affected compile/Ruff checks,
`mypy` over 40 source files, frontend full typecheck/lint, a final 18-page
production build, additive OpenAPI export and four changed Markdown files.
Its citation/hash codec compatibility and bounded policy lookup were inspected
statically; no runtime persistence, provider, quarantine or browser result is
claimed. The availability projection limits each read to eight release groups,
four concurrent calls and a four-second overall deadline.

Automatic CI on `cc7c07e` passed five checks and failed backend/frontend verify:
1,147 backend tests passed with five failures; 788 frontend tests passed with
seven failures. Static classification traced backend failures to old imprecise
original pins and most frontend failures to old actor-lookup or deliberate
renewal assumptions. It also found a real focus defect: scope renewal focused
a select while busy disabled it. Final fix `f7f7b9e` addresses it on static inspection.
Fixtures were not changed and suites were not rerun under the waiver. CI remains
a material failed gate until an actual later run demonstrates otherwise.

Follow-up automatic run `37908735687` on `96ec278` recorded 1,142 backend passes,
ten failures and three expected failures; frontend recorded 778 passes and
17 failures. Four source assertions exposed two actual regressions: malformed
attestation lost its specific diagnostic, and a malformed legacy hit discarded
valid sibling hits. Both were addressed in `f7f7b9e` and independently re-reviewed.
The isolated producer test omitted the new sibling-module import
context; the supported Docker layout includes it, but container execution remains
unverified. Ten new conversation failures used a facts-module mock missing
`listTransactions`, which produced an additional selector alert. Inspection
confirmed that real parent refusal/retry controls were retained and separate.
These classifications preserve the failed gates; they do not establish that
any later test run passed. No fixture or assertion was adapted.

No production source approvals, signing keys, provider choices, model settings,
legal template text or approval/waiver wording were created or changed. Human
visual and Sinhala terminology review remains outstanding. Source availability
is not a complete/current-law assertion. Ten-form expansion was not authorized.
The new Form 8 migration was inspected but not applied after the waiver.
Request-local evidence-read reuse is implemented; its performance improvement
has not been measured.

## Local real-case walkthrough evidence

The owner attested a client approval letter; the letter was not independently
inspected. Existing authorized provider/GCS flags were already enabled and were
not enabled by the agent. Private case material stayed out of committed fixtures
and review artifacts. Only aggregate observations are recorded here.

Seven PDFs contained 26 OCR-dependent pages. An initial provider pass completed
five sources and timed out on two; serial recovery completed both. On frozen
`2a4ff94`, normal application processing APIs later persisted seven terminal
successes and 113 unreviewed canonical candidates. A separate process read the
same candidates and unchanged originals; foreign actors received 404.

All candidates had source/page references and page text: 106 text-level and
seven page-level attributions. Literal matching and counts do not demonstrate
semantic correctness, grouping, roles, resolved conflicts or lawyer verification.
No final upload-to-reviewed-facts-to-conversation-to-draft real-case journey was
performed. The canonical read took 193.687 seconds and repeated evidence
downloads; readiness took 203.719 seconds and correctly remained unknown.
Later reuse/deadline repairs have not been remeasured.

Handling disclosure: private handling instructions with identifying content,
and later opaque private identifiers, were inadvertently emitted to tool output
before subsequent output was redirected/sanitized. No real values, images or
identifying logs were committed or included in review artifacts. This limits
any claim of zero exposure during local operation.

## Owner decisions remaining

- Review exact source content, rights, audience permissions and signing custody
  before publishing the staged legal release.
- Validate prescribed Form 8 template/layout, Sinhala terminology and visual
  workflow against concrete synthetic artifacts.
- Execute the waived full extraction benchmark and final migrated synthetic
  end-to-end acceptance when the owner chooses to restore that verification.
- Review outstanding CI failures and merge/deploy through the human-owned process.

## Final review and ordered commit map

The integrated review covered `a87e356..96ec278`: 37 commits, 452 paths and
3,650,909 bytes. It structurally inspected the complete package and semantically
inspected named coupled integration paths. Each product slice also had a full
independent scoped review. The final review did not inspect every changed line
semantically or rerun tests. Its three findings plus two newly observed CI
product regressions were fixed in one six-path commit, `f7f7b9e`.

One independent scoped re-review read the complete 20,614-byte fix package and
approved all five fixes with no new blocking finding. This closes the scoped
code review. Failed CI, runtime acceptance, extraction targets and human gates
remain outstanding. The worktree is retained for PR feedback.

| Reviewed slice | Finding and resolution | Accepted follow-up |
| --- | --- | --- |
| Processing | Pagination explanation, late-matter response guard and unavailable-status regression corrected | `fb90e8b` |
| Canonical facts | Cross-transaction compatibility, parcel-specific search authority, grouping currentness, resolved alternatives, unavailable OCR and explicit scope review boundaries corrected | `07d45f2` |
| Fact register | Displayed transaction edit retains its exact reviewed scope/version; missing reference cannot become creation | `b6a48f7` |
| Document corrections | Explicit edit renewal, manual recovery path, historical/original viewer labels, committed API and unavailable-derivative fallback corrected | `9957ab7` |
| Checklist/readiness | Partial stale evidence withdraws review authority; human original inspection routes to its actionable Checks control | `493ffa6` |
| Conversation | Transport-outage accounting, actual source attestation, accepted-send recovery and enum labels corrected; receipt lookup made genuinely read-only | `ccce896`, `06fff56` |
| Form 8 | Every scoped binding must remain current; an intent uses one captured actor credential across lookup and POST | `003ce38` |
| Processing repair | Reused ambiguous intents survive subsequent refusals until deliberate renewal | `cc7c07e` |
| Source core | Explicitly approved internal snippets permitted without public/full-reader/download authorization | `f4a35ec` |
| Source retrieval | Governed deployment intent fails closed if release artifact is missing, before legacy API import | `1417bec` |
| Dated conversation | Scope/date/result/history codecs and current-policy projection approved; distinct coverage reasons corrected in final fix | `407fb1b`, `f7f7b9e` |
| Final integration | Enabled-render keyboard focus, distinct EN/SI source gaps, consistent legacy/governed deployment advice, specific attestation diagnostics and legacy partial-hit handling corrected | `f7f7b9e` |

These slice re-reviews reported no new blocking issue within their fix scope.
They do not replace whole-branch acceptance. Existing Starlette/httpx and Alembic
configuration warnings, shell accessible-name advisory, older Lighthouse runtime
and snapshot limitations remain disclosed maintenance/review debt.

Final scoped commands on `f7f7b9e` passed:

| Cwd | Command | Result |
| --- | --- | --- |
| frontend | `pnpm.cmd exec eslint src/components/matter/fact-input.tsx src/components/matter/legal-source-context.tsx --max-warnings=0` | Passed |
| frontend | `pnpm.cmd exec prettier --check src/components/matter/fact-input.tsx src/components/matter/legal-source-context.tsx src/lib/i18n/messages/en.json src/lib/i18n/messages/si.json` | Passed |
| frontend | `CI=true pnpm.cmd build` | Exit 0, 41-second compile, 18/18 pages |
| frontend | `pnpm.cmd typecheck` after build | Exit 0 |
| backend | `uv run --no-sync python -m compileall -q src/modules/research/infrastructure/retrieval/http_adapter.py` | Exit 0 |
| backend | `uv run --no-sync ruff check src/modules/research/infrastructure/retrieval/http_adapter.py` | Exit 0 |
| backend | `uv run --no-sync ruff format --check src/modules/research/infrastructure/retrieval/http_adapter.py` | Exit 0 |
| backend | `uv run --no-sync mypy src/modules/research/infrastructure/retrieval/http_adapter.py` | Exit 0, one source file |
| root | `pnpm.cmd exec markdownlint-cli2 --no-globs deploy/PRODUCTION.md` | One file, zero errors |
| root | `git diff --cached --check` and explicit staged privacy inspection | Passed |

An intermediate typecheck caught a misplaced focus reference, and diff review
caught encoding corruption in newly written Sinhala labels. Both were corrected
before commit. A concurrent Next-generated-types check failed transiently; the
sequential final typecheck passed without a product/configuration workaround.

The ordered feature commit table below follows first-parent history. Upstream
PR97 Vision wiring, the human merge of PR98, and PR99 manual production promotion
are preserved by `96ec278`; their external commits are not attributed to this
implementation. The delivery documentation commit containing this report follows
the listed code commits. Objectives refer to the seven numbered requirements;
"statutes" denotes the separately approved amendment/date extension.

| Commit | Objectives | Verification | Change |
| --- | --- | --- | --- |
| `7fcfa79` | All | Approved design | docs(e8-7): plan the lawyer-led matter workflow |
| `1702a60` | 1,7 | Reviewed; pre-waiver checks | fix(e8-7): preserve processing outcomes and recovery |
| `fb90e8b` | 1,7 | Reviewed; pre-waiver checks | fix(e8-7): guard processing refresh and recovery errors |
| `ad6571b` | 2,3,7 | Reviewed; pre-waiver checks | feat(e8-7): preserve scoped fact projections |
| `95e955d` | 2,3,7 | Reviewed; pre-waiver checks | feat(e8-7): review scoped matter facts |
| `07d45f2` | 2,3,7 | Reviewed; pre-waiver checks | fix(e8-7): enforce scoped fact review boundaries |
| `3cbb335` | 2,3,7 | Reviewed; pre-waiver checks | feat(e8-7): expose the canonical matter fact register |
| `b6a48f7` | 2,3,7 | Reviewed; pre-waiver checks | fix(e8-7): preserve reviewed transaction scope versions |
| `61f19ea` | 1,2,7 | Reviewed; pre-waiver checks | fix(e8-7): invalidate and refresh document interpretations |
| `ca6b8e8` | 1,3,7 | Reviewed; pre-waiver checks | fix(e8-7): recover document groups and replay ingestion commands |
| `404ac5a` | 1,2,3,7 | Synthetic review evidence | docs(e8-7): record synthetic document correction review |
| `9957ab7` | 1,2,3,7 | Reviewed; pre-waiver checks | fix(e8-7): renew document edits and recover manual review |
| `2a4ff94` | 1,2,7 | Reviewed; API processing observed | fix(e8-7): recognize governed documents before checklist routing |
| `e0eb268` | 3,5,7 | Reviewed; pre-waiver checks | feat(e8-7): pin requirement evidence and human original inspections |
| `bded7b0` | 2,5,6,7 | Reviewed; pre-waiver checks | fix(e8-7): preserve scoped check and output freshness |
| `596f2df` | 5,7 | Reviewed; pre-waiver checks | feat(e8-7): expose conservative matter readiness and next actions |
| `493ffa6` | 3,5,7 | Reviewed; pre-waiver checks | fix(e8-7): withdraw partial evidence review and route human work |
| `7440a6d` | 4,7 | Reviewed; pre-waiver checks | fix(e8-6): recover failed assistant turns without duplicate messages |
| `21fe19e` | 3,4,5,7 | Reviewed; pre-waiver checks | feat(e8-7): share persistent matter conversation and grounded tools |
| `ccce896` | 4,7 | Reviewed; pre-waiver checks | fix(e8-6): attest research sources and reconcile accepted sends |
| `06fff56` | 4,7 | Reviewed; pre-waiver checks | fix(e8-6): keep send receipt lookups read-only |
| `8170c77` | Statutes | Approved design; Markdown | docs(e8-7): record approved statute discovery scope |
| `b2252a0` | 2,6,7 | Reviewed; static/build only | feat(e7): bind Form 8 to reviewed transaction facts |
| `003ce38` | 6,7 | Reviewed; static/build only | fix(e7): preserve scoped freshness and actor retry identity |
| `633525b` | Statutes | Reviewed; static only | feat(e8-7): validate reviewed legal source releases |
| `f4a35ec` | Statutes | Reviewed; static only | fix(e8-7): retain approved internal source snippets |
| `720a154` | 1,2,3,5,7 | Reviewed; static/build only | fix(e8): bound workflow processing and pin reviewed evidence |
| `cc7c07e` | 2,3,7 | Reviewed; static only; CI red | fix(e8): retain ambiguous intents until deliberate renewal |
| `bbfe80d` | 4,7,statutes | Reviewed; static/build only | feat(e8-7): retrieve related legal authorities with release metadata |
| `1417bec` | 4,7,statutes | Reviewed; static only | fix(e8-7): prevent governed retrieval legacy downgrade |
| `407fb1b` | 4,7,statutes | Reviewed; static/build only | feat(e8-7): show scoped statute and amendment date contexts |
| `96ec278` | Baseline | Clean merge; two-doc Markdown | chore(e8-7): integrate current deployment baseline |
| `f7f7b9e` | 2,3,4,7,statutes | All five fixes reviewed; static/build only | fix(e8): resolve integrated workflow review findings |

See [extraction coverage](extraction-coverage.md), [ordered rulings](rulings.md), and the [legal source review packet](legal-source-review-packet.md) for the approved reference, decision costs and outstanding source approvals.
