# Service definition of done

Companion to `backend/backend-implementation-plan-v0.md` §9,
`services/README.md`, `events.md`, `security-model.md`,
`api-conventions.md`, and `jobs-and-workers.md`.

A service doc describes what to build. This file describes **how you know it is
finished**. Nothing is "done" because the endpoints return 200; it is done when
the gates below pass in CI and the acceptance row in §6 is green.

Three ideas run through it:

1. **Most correctness rules are the same for every service.** Organisation
   isolation, 404-not-403, audit-on-mutation, event-registry parity,
   idempotency, pagination. Those are written once as a **conformance suite**
   parameterised over the service registry, so a new service is covered the day
   it registers rather than the day someone remembers to copy the tests.
2. **The rest are specific**, and each service's own doc already lists them in
   its test section. §6 pins those to the gate they satisfy.
3. **A gate that cannot fail is not a gate.** Every item below names the
   observable failure, not an intention.

## 1. The five levels

A service moves through these in order. Level names appear in
`services/README.md` so the catalogue always shows real status.

| Level | Meaning | Gate |
| --- | --- | --- |
| `L0 designed` | Doc merged, decisions closed or explicitly open | §2 |
| `L1 contracted` | Schemas, enums, events, and OpenAPI fixtures exist and are shared with the frontend | §3 |
| `L2 conformant` | The cross-service conformance suite passes for this service | §4 |
| `L3 functional` | Service-specific unit, integration, and security tests pass | §5 |
| `L4 accepted` | The plan phase exit gate and any legal-review item are signed off | §6 |

A service may sit at `L3` indefinitely if its legal content is blocked — that
is a legitimate state, not a failure. `content-governance-service.md` §4 already
distinguishes delivery phase from content readiness, and this ladder does the
same.

## 2. L0 — designed

- [ ] Doc exists under `docs/services/` and is listed in `services/README.md`.
- [ ] Header states owner, phase, status level, and last-reviewed date.
- [ ] "What it owns" and "what it does not own" are both present, and every
      "does not own" names the service that does.
- [ ] Every port it depends on is named, and each is either defined in that
      port's owning doc or defined here.
- [ ] Every event it publishes or consumes is registered in `events.md`.
- [ ] Invariant table exists and includes the four universal rows: organisation
      isolation, matter isolation (if matter-scoped), audit on mutation, and
      metering (if the service performs paid work).
- [ ] Failure modes section exists and covers the partial-failure cases, not
      only the happy-path refusals.
- [ ] Open decisions are either closed with a stated default or marked as a
      named review item with an owner. "Lean X" with no decision is not L0.
- [ ] `npx markdownlint-cli2` clean.

## 3. L1 — contracted

- [ ] Pydantic request and response schemas exist in the owning module's `api/`
      package (or its flat `schemas.py` while small), and no domain object is
      serialised directly.
- [ ] Every legal-state field is a closed enum, not a free string.
- [ ] OpenAPI regenerated into `backend/contracts/openapi.v1.json`, and the diff
      is either additive or accompanied by an entry in
      `frontend-contract-migration.md`.
- [ ] Contract fixtures exist under `tests/contract/fixtures/<service>/` and are
      the only example payloads referenced by frontend work.
- [ ] Event payload schemas registered and validated against `events.md` §2.
- [ ] Error codes added to the owning module's `domain/errors.py`; shared safe
      HTTP mapping remains in `platform/errors.py`.
- [ ] Any frontend type this service breaks is recorded in
      `frontend-contract-migration.md` with a mapping.

## 4. L2 — the conformance suite

These live in `tests/conformance/` and are **parameterised over the service
registry** in `services/README.md` §2. Adding a service to the registry adds it
to every test below. A service that cannot yet satisfy one declares an explicit,
reviewed exemption in the registry — exemptions are visible, not silent.

### 4.1 Tenancy and access — `test_tenancy.py`

1. Every route rejects a resource belonging to another organisation with 404.
2. Every matter-scoped route rejects a non-member with 404, and the response
   body and timing match a genuinely missing resource.
3. Every mutating route rejects an actor lacking the declared capability with
   403 `capability_denied`, and the denial is audited.
4. A forged `role`, `organisationId`, `actorId`, or capability in a request body
   is ignored.
5. Every persisted table the service owns has a non-null `organisation_id`
   column. This is a schema test, not a behaviour test — it catches the table
   somebody added without thinking about tenancy.

### 4.2 Audit — `test_audit_coverage.py`

1. **Every mutating application method produces exactly one audit event.** The
   test enumerates public mutating methods by reflection, calls each against a
   fixture, and asserts the count. A method that writes without auditing fails
   the build; this is the release blocker in plan §9.2 made mechanical.
2. Mutation and audit commit or roll back together, including from a worker and
   from a provider webhook handler.
3. Audit rows carry a non-null `organisationId` and `correlationId`.
4. Reason-required actions reject without a reason.
5. Audit payloads contain no value matching the private-content denylist.
6. No update or delete path exists on the audit store.

### 4.3 Events — `test_event_registry.py`

1. Every event the service publishes is in `events.md`, and vice versa.
2. Every event it consumes has exactly one registered publisher.
3. Names match `^[a-z][a-z-]*\.[a-z][a-z0-9-]*$` and use a registered aggregate.
4. Every published payload validates against the envelope schema.
5. No payload field matches the private-content denylist.
6. Every consumer processes the same event twice and produces one effect.
7. Every event is written to the outbox in the mutation's transaction; a
   rollback leaves no outbox row.

### 4.4 API shape — `test_api_conventions.py`

1. Every list route paginates, caps `limit` at 100, and returns the `page`
   envelope.
2. Every mutating route on a versioned aggregate requires `If-Match` and returns
   412 on a stale version, 428 on a missing one.
3. Every creating POST in the required set honours `Idempotency-Key`: a replay
   returns the stored response, a different body under the same key is 409.
4. Every error response matches the envelope and uses a code from the catalogue.
5. No route holds the request open for OCR, retrieval, rendering, or
   transcription; each returns a job envelope.
6. `correlationId` is echoed on every response and present on every audit row
   and event produced by the request.

### 4.5 Jobs — `test_job_contract.py`

For every job type the service owns (`jobs-and-workers.md` §5):

1. Enqueue and state change commit atomically.
2. Duplicate delivery produces one effect.
3. A reaped lease re-claims the job exactly once.
4. Retryable failures back off; permanent failures do not retry.
5. Exhausted attempts land in `dead_letter` and raise the alert.
6. A failed job leaves the source aggregate unchanged and no reachable partial
   artefact.

### 4.6 Metering — `test_metering.py`

For every operation the service declares as metered:

1. The operation calls `require_feature` before doing work, and fails closed
   when the feature is absent.
2. It reserves before the work and consumes after it, keyed by a stable
   `operation_id`.
3. A retry of the same `operation_id` does not double-charge.
4. A terminal failure releases the reservation.
5. Quota exhaustion returns 429 `quota_exhausted` with the metric named, and no
   partial work is performed.
6. Restricted mode blocks the new paid operation but not reads of existing
   records.

### 4.7 Privacy — `test_privacy.py`

1. No log line, error body, event payload, audit payload, notification body, or
   metric label contains a value matching the denylist (party-name keys, NIC and
   passport patterns, `snippet`, transcript `text`, extracted `value`,
   suspicion narrative, recipient address, secrets, tokens).
2. Restricted-compliance records return no existence signal to an ordinary
   member.
3. Encrypted-at-rest fields are absent in plaintext from a database dump of the
   service's tables.

## 5. L3 — service-specific tests

Each service doc already carries a test list. L3 requires that list to be
implemented and passing, at these minimum layers:

| Layer | Minimum |
| --- | --- |
| Unit | Every state machine transition, legal and illegal; every domain refusal |
| Contract | Every request and response schema; every event payload |
| Integration | The service's primary path over real PostgreSQL plus storage or queue emulators, and its supersession/invalidation path |
| Security | The service-specific rows in its own test list, beyond the conformance suite |
| Evaluation | Only where the doc names one (document-processing, check-service, research-service, memory-service, voice-service) |

Two rules keep this honest:

- **A test list item removed from the doc must be removed in a commit that says
  why.** Silently dropping a test is the same as silently dropping a gate.
- **Coverage is not the metric.** The metric is that every invariant row in the
  service's own table has a test that fails when the invariant is violated.
  `tests/conformance/test_invariant_coverage.py` checks that mapping exists —
  every invariant row must name at least one test id.

## 6. L4 — acceptance matrix

Status column is the current level. Update it in the same commit that moves the
service.

| Service | Phase | Specific acceptance gate | Status |
| --- | --- | --- | --- |
| `auth_service` | 2 | Reviewer cannot approve; non-member gets 404; expired practice certificate blocks the gated capabilities | L0 |
| `billing_service` | 2B | Forged checkout return grants nothing; duplicate and out-of-order webhooks cannot duplicate or regress state; payment failure preserves records and exports | L0 |
| `matter_service` | 2 | Client cannot write phase, progress, blocking, or readiness; reclassification appends and never overwrites | L0 |
| `party_service` | 2 | Full identifier never returned without capability plus recorded purpose; no plaintext identifier in a table dump; no automatic identity merge | L1 |
| `document_service` | 3 | Upload acknowledgement independent of OCR; provider failure preserves the original; 15-document matter reaches review or explicit failure within the V0 target | L0 |
| `storage_service` | 3 | Every original is a conditional write pinned to an exact provider generation; cross-tenant grants fail; held records and unknown inventory are never deleted; Neon/GCS partial failures reconcile without data loss | L0 |
| `document-processing` | 3 | Ladder routes correctly per confidence and box state; coordinates map exactly across DPI and rotation; no auto-accept; adapter refuses real data before the provider approval flag is set | L0 |
| `verification_service` | 4 | Every accepted particular opens the exact source version, page, and region; unreadable evidence stays blocked; record rebuilds without changing decisions | L0 |
| `check_service` | 5 | Every active rule has authority, version, effective date, and passing fixture tests; pass/warning/fail/needs-review stay distinct; labelled evaluation reports precision, recall, abstentions | L0 |
| `task_service` | 5 | Unknown never means not-applicable; mandatory block needs evidence or a recorded override; compilation is reproducible from pinned versions | L0 |
| `obligations_service` | 5 | No authoritative deadline without an approved rule and a lawyer confirmation; each of the three registration branches resolves correctly on fixtures; nil month still produces a return | L0 |
| `notarial_register_service` | 5 | Register serials gapless per notary and year; attestation requires an approved and exported instrument; practising jurisdiction snapshotted | L0 |
| `research_service` | 6 | Every retained claim resolves to a passage and authority status; unsupported questions abstain; corpus cannot query matter storage; latency measured against the V0 target | L0 |
| `corpus_governance_service` | 6 | Unknown or denied sources fail closed; restricted records cannot enter the public catalogue; a release reproduces from its signed manifest | L0 |
| `library_service` | 6 | Metadata-only never returns text; no CommonLII source document reachable; no matter document enumerable | L0 |
| `content_governance_service` | 5, 7 | Approved definitions immutable; locked wording fixed at approval; placeholder prescribed text blocks approval; check-rule approval verifies the predicate registry and fixtures | L0 |
| `draft_service` | 7 | Unverified fact cannot reach a saved version; altered locked wording cannot persist; **create → submit → approve → export completes end to end** | L0 |
| `approval_service` | 7 | No mandatory unverified fact reaches approval; no hidden placeholder; approval never covers changed content; superseded evidence invalidates the approval | L0 |
| `export_service` | 7 | Export only on an approved version; manifest identifies exact draft, template, and fact versions; English and Sinhala output survives reopen validation | L0 |
| `memory_service` | 6 | Nothing here feeds a draft; every episode reconstructable from an authoritative store; corrections invalidate; cross-matter isolation | L0 |
| `notification_service` | 5 | Delivery failure never mutates an obligation; each channel sends at most once; restricted alerts carry no context; no authentication email routed here | L0 |
| `voice_service` | V0 or V1 by schedule | Provider transcript is always a candidate; no silent verification, wording change, approval, or downstream call; version history preserved; benchmark thresholds met before live use | L0 |
| `retention_service` | 8 | Nothing destroyed automatically; a hold beats every policy at both approval and execution; tombstone precedes destruction; audit out of scope | L0 |
| `audit_service` | all | Every mutating method across every service produces exactly one event; chain verification detects tampering; feed filtered by organisation, membership, and capability | L0 |

`party_service` is at `L1`, not higher, and the reason is the ladder rather than
the service: `L2` is the registry-parameterised conformance suite, and
`tests/conformance/` is empty for every service. The three named acceptance
gates above are all covered by passing party-local tests — a full identifier is
returned only to a caller holding `party.read-identity` who supplies a purpose
that is written to the audit event, a dump of all six party tables contains no
plaintext identifier, and the duplicate probe surfaces candidates while merging
is a separate administrator-only method. Its registry exemptions in
`contracts/services.yaml` name what is still missing.

## 7. Release-blocking gates

Plan §9.2 lists conditions under which the backend cannot be accepted at all.
Each maps to a named test that must be green **before any release**, regardless
of which services are done:

| Release blocker | Test |
| --- | --- |
| Invented citation | `research/test_citation_validation.py::test_unbacked_claim_dropped` |
| Unsupported retained legal claim | `research/test_abstention.py::test_no_valid_citation_abstains` |
| Cross-matter disclosure | `conformance/test_tenancy.py` (all services) |
| Cross-organisation disclosure | `conformance/test_tenancy.py` (all services) |
| Silent original loss | `documents/test_immutability.py::test_put_immutable_rejects_existing_key` |
| Mandatory unverified fact in an approved export | `approval/test_fact_gate.py`, `export/test_approved_only.py` |
| Altered locked wording | `drafts/test_locked_blocks.py`, `export/test_render_uses_pinned_document.py` |
| Hidden placeholder | `approval/test_placeholder_gate.py` |
| Missing audit event | `conformance/test_audit_coverage.py::test_every_mutation_audited` |
| Approval attached to changed content | `approval/test_hash_pin.py`, `drafts/test_submit_pin_invalidated_by_save.py` |
| Legal source crossing its approved boundary | `corpus/test_audience_enforcement.py` |

## 8. CI wiring

```text
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract
uv run pytest tests/conformance          # §4, parameterised over the registry
uv run pytest tests/integration          # needs PostgreSQL, MinIO, queue
uv run pytest tests/security
uv run pytest tests/e2e                  # the full matter-to-export path
uv lock --check
npx markdownlint-cli2
```

Conformance runs on every pull request. Integration and e2e run on every merge
to `main` against a Neon branch database (`infrastructure.md` §3). The
release-blocking set in §7 runs on both and is never skipped, never marked
`xfail`, and never quarantined — a flaky release-blocker is fixed, not muted.

## 9. Registry file

The conformance suite reads a machine-readable registry so it does not parse
Markdown at test time. `backend/contracts/services.yaml`:

```yaml
- name: draft_service
  doc: docs/services/draft-service.md
  level: L0
  phase: 7
  matter_scoped: true
  routes_prefix: /api/v1/matters/{matterId}/drafts
  capabilities: [draft.create, draft.save, draft.restore, draft.submit-for-review]
  publishes: [draft.created, draft.version-saved, draft.version-restored,
              draft.review-requested]
  consumes: [document.version-superseded, particular.evidence-stale,
             workflow.readiness-changed]
  metered: []
  owns_tables: [drafts, draft_versions]
  jobs: []
  exemptions: []
```

`services/README.md` §2 is generated from this file, so the catalogue and the
tests cannot disagree. A drift check (`test_registry_matches_readme`) fails the
build if someone edits one and not the other.
