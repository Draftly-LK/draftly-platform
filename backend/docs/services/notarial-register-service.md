# notarial_register_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`obligations-service.md`, `task-service.md`, `export-service.md`,
`retention-service.md`, `content-governance-service.md`, and `events.md`.

This service was missing. `obligations-service.md` §7.2 builds the monthly deed
return "from deeds attested in the previous month" and §7.3 calculates the
registration deadline from "the attestation date"; `content-governance-service.md`
§4.1 marks `notarial-form-f-register` and the protocol templates as `mvp`.
**No service recorded an attestation, a protocol number, a register entry, or a
deed serial**, so two of the ten V0 obligations were uncomputable and three
events (`document.attested`, `document.registration-acknowledged`,
`document.collection-ready`) had consumers and no publisher.

It is the notary's statutory record-keeping tier. It is deliberately separate
from `document_service` (which owns uploaded evidence) and from `draft_service`
(which owns the instrument's text): an attestation is a legal act performed by a
named notary, not a state of a file.

## 1. What it owns

The notary's own records:

- the **Attestation** — the act, its date, the acting notary, the practising
  jurisdiction at the time, the executants and witnesses present, and the
  attestation clause variant used;
- the **protocol** — original, duplicate, and certified copies, with custody and
  location;
- the **register (Form F)** — the sequential deed register per notary, with the
  serial number and the entries the Ordinance requires;
- the **monthly return period** — the aggregate of instruments attested in a
  calendar month, its components, and its submission and acknowledgement state;
- the **registration lifecycle** after attestation — submission to the registry,
  acknowledgement, defect responses, and collection.

It does **not** own: the instrument's wording (`draft_service`), the rendered
file (`export_service`), the deadline calculation (`obligations_service` runs
approved rules against `instrument.attested`), the workflow steps around
execution (`task_service`), the attestation-clause template
(`content-governance-service` owns `notarial-form-e-attestation`), or retention
and destruction (`retention_service`).

## 2. Where it sits

```text
POST /api/v1/matters/{id}/attestations
GET  /api/v1/matters/{id}/attestations/{attId}
POST /api/v1/attestations/{id}/protocol
POST /api/v1/attestations/{id}/registration-submission
POST /api/v1/attestations/{id}/registration-acknowledgement
POST /api/v1/attestations/{id}/collection
GET  /api/v1/register/entries
GET  /api/v1/register/periods
POST /api/v1/register/periods/{id}/certify
              |
              v
      api/v1/register.py
              |
              v
 application/notarial_register_service.py
              |
              +--> AttestationRepository
              +--> RegisterRepository
              +--> DraftReadPort / ExportReadPort
              +--> PartyReadPort
              +--> NotaryProfilePort
              +--> EventPort / AuditPort
```

Register entries are **notary-scoped**, not matter-scoped: the serial sequence
belongs to the notary, spans matters, and is organisation-bounded. Matter
membership gates the attestation routes; the register routes are gated by
`instrument.attest` plus ownership of that register.

## 3. Domain models

### 3.1 Attestation

```text
Attestation
  id
  organisationId
  matterId
  instrumentKind                    # transfer | gift | lease | mortgage | poa | ...
  registrationRegime                # deed | rta | condominium | special-area
  sourceKind = export | external
  exportId?                         # the approved rendered instrument
  draftVersionId?
  contentHash?
  attestationClauseDefinitionId
  attestationClauseVersion
  attestationConditions             # read | read-and-explained | attorney |
                                    # illiterate | impression | corporate | multiple-notaries
  notaryUserId
  practisingJurisdictionId          # at the moment of attestation
  registrationJurisdictionId
  instrumentLanguage
  attestedAt                        # date and time, Asia/Colombo
  placeOfExecution
  executants                        # party refs + capacity + evidence refs
  witnesses                         # party refs + evidence refs
  considerationRecorded?
  state
  version
```

`practisingJurisdictionId` is snapshotted at attestation, not read live from the
notary profile later. The deed-registration deadline branch (30 vs 60 days)
depends on whether registration is inside or outside the notary's practising
jurisdiction *at the time of attestation*, and a later profile change must not
retroactively move a deadline (`obligations-service.md` §7.3).

```text
AttestationState =
  draft | attested | registration-submitted | registration-acknowledged |
  registration-defective | registered | collected | cancelled
```

`attested` is terminal in one direction: an attestation is never edited. A
mistake is corrected by a new instrument and a recorded cancellation with a
reason, not by rewriting the record.

### 3.2 RegisterEntry (Form F)

```text
RegisterEntry
  id
  organisationId
  notaryUserId
  registerYear
  serialNumber                      # sequential per (notary, registerYear)
  attestationId
  entryDate
  instrumentKind
  partySummaryRef                   # references, not names
  considerationRef?
  folioRef?
  state = active | cancelled
  cancellationReason?
  createdAt
```

- `serialNumber` is allocated by a database sequence per
  `(notary_user_id, register_year)` inside the attestation transaction. Gaps are
  not permitted; a cancelled entry keeps its serial and is marked `cancelled`.
- The register holds **references**, not copied party names or property
  descriptions. The rendered Form F output resolves those references at render
  time through `export_service`, under the caller's permissions.

### 3.3 ProtocolRecord

```text
ProtocolRecord
  id
  attestationId
  copyKind = original | duplicate | certified-copy | office-copy
  storageRef?                       # digital copy, when one exists
  physicalLocation?
  custodianUserId
  issuedTo?
  issuedAt?
  returnedAt?
  retentionClass
  state = held | issued | returned | transferred | destroyed
```

Physical custody is tracked because the Ordinance requires the notary to
preserve the protocol. `retentionClass` is set here and enforced by
`retention_service`; nothing in this service deletes.

### 3.4 MonthlyReturnPeriod

```text
MonthlyReturnPeriod
  id
  organisationId
  notaryUserId
  periodStart
  periodEnd
  instrumentIds
  isNilReturn
  components                        # deed list | duplicates | applicable copies | nil return
  componentStates
  certifiedBy?
  certifiedAt?
  submittedAt?
  acknowledgedAt?
  state = open | closed | certified | submitted | acknowledged
  version
```

The period is generated by the `register.close-month` scheduled job
(`jobs-and-workers.md` §6) at the start of the following month, closing the
previous one and publishing `register.monthly-period-closed`.
`obligations_service` turns that event into the due-by-the-15th obligation. If
no instrument was attested, `isNilReturn` is true and the nil-return component
applies — the obligation still exists.

## 4. Ports

- `AttestationRepository`, `RegisterRepository` — persistence with optimistic
  concurrency and the per-notary serial sequence.
- `DraftReadPort` / `ExportReadPort` — resolve the approved draft version and
  the rendered export whose content hash the attestation pins.
- `PartyReadPort` — resolve executant and witness party references and confirm
  their identity evidence state. This service never stores identity values.
- `NotaryProfilePort` — the acting notary's registration number, practising
  jurisdiction, and current practice-certificate status
  (`security-model.md` §3.3).
- `ContentReadPort` — the approved `notarial-form-e-attestation` definition and
  the clause variant for the recorded conditions.
- `EventPort`, `AuditPort`.

## 5. Methods

### record_attestation(ctx, matter_id, input) -> AttestationRead

The load-bearing method.

1. Re-check matter membership; 404 for a non-member.
2. Require `instrument.attest` **and** a current practising notary
   (`security-model.md` §3.3). An expired practice certificate blocks
   attestation; it does not warn.
3. Require an approved, exported instrument: load the Approval and the Export,
   and pin `contentHash`. Attesting an instrument that was never approved is
   refused. An `external` source (a paper instrument prepared outside Draftly)
   is permitted only with a recorded reason and an uploaded document version.
4. Resolve executants and witnesses through `PartyReadPort`. Every executant
   must have identity evidence in `verified` state; a `recorded`-only executant
   blocks with the specific party named.
5. Select the approved attestation-clause variant for the recorded conditions.
   A condition combination with no approved clause is refused as a governance
   error, never improvised (`content-governance-service.md` §4.1).
6. Snapshot `practisingJurisdictionId` and `registrationJurisdictionId`.
7. Allocate the register serial and write `Attestation`, `RegisterEntry`,
   `ProtocolRecord(original)`, the audit event, and the outbox event in one
   transaction.
8. Publish `instrument.attested`.

### record_registration_submission / acknowledgement / defect / collection

Each advances `AttestationState`, records the registry reference, timestamps,
and publishes the matching `instrument.*` event. A defect response reopens the
registration follow-up obligation rather than closing it.

### certify_period(ctx, period_id) -> MonthlyReturnPeriodRead

Requires `register.certify-return` and a practising notary. Freezes the
instrument set, records the certifier, and moves the period to `certified`. The
rendered return itself is a supporting-document render
(`export-service.md` §11) against `notarial-form-f-monthly-return` or the
nil-return template.

### list_register_entries(ctx, filters) -> page[RegisterEntryRead]

Notary-scoped and organisation-scoped, paginated (`api-conventions.md` §2).
An administrator may read another notary's register within the same
organisation; nobody may read across organisations.

## 6. Entitlement and metering

`instrument.attest` requires `require_feature(org, "attestation.enabled")`.
Attestations are counted with `reserve_usage(org, "attestations.monthly", 1,
operation_id=attestation_id)` consumed on commit. A monthly-return render is
metered as an ordinary `report.render`.

## 7. What this service refuses to infer

- It never derives the registration deadline. It publishes
  `instrument.attested` with both jurisdictions and the verified regime;
  `obligations_service` selects an approved rule.
- It never guesses jurisdiction from an address string
  (`obligations-service.md` §7.3).
- It never treats a rendered PDF as an attestation. Rendering is
  `export_service`; attesting is a recorded human act.
- It never back-dates. `attestedAt` may be earlier than the record time only
  with an explicit reason and a separate audit action, and the delta is stored.

## 8. Invariants

| Invariant | Enforcement |
| --- | --- |
| Attestation follows approval | Requires an `approved` version and a rendered export, and pins its content hash |
| Attestation is immutable | No update path; correction is a new instrument plus a recorded cancellation |
| Register serials are gapless per notary and year | Database sequence allocated inside the attestation transaction; cancelled entries retain their serial |
| Practising jurisdiction is snapshotted | Stored on the attestation, never re-read from the profile |
| Only a current practising notary attests | `instrument.attest` plus `require_practising_notary` |
| Executants are identity-verified | Every executant needs `verified` identity evidence before attestation |
| Clause variants are governed | Only approved `notarial-form-e-attestation` variants; an unmatched condition set is refused |
| The register stores references | No copied party names or property descriptions in register rows |
| Monthly periods are complete | The scheduler closes every month, nil returns included |
| Protocol is preserved, never deleted here | `retention_service` owns destruction; this service records custody |
| Every act audited | `AuditPort.record` with `targetType: "instrument"` |

## 9. Failure modes

- Attestation attempted on an unapproved or edited draft — refused; the approval
  pins a hash and an edit forks a new unapproved version
  (`approval-service.md` §5).
- Practice certificate expired on the attestation date — refused, with the
  annual-certificate obligation surfaced as the blocker.
- Executant identity evidence only `recorded` — refused, naming the party.
- Two attestations race for a serial — the sequence serialises; no duplicate
  serial is possible.
- An attestation is cancelled — the register entry becomes `cancelled` with a
  reason, the serial is retained, the registration obligation is cancelled with
  a reason, and the monthly return excludes it while retaining the history.
- The month closes while an attestation is mid-transaction — the period is
  computed from committed rows only, and a late commit lands in the following
  period with a recorded exception rather than silently amending a closed one.
- No instruments in the month — a nil-return period is created; the obligation
  is not skipped.
- Registry returns a defect — state moves to `registration-defective`, the
  original deadline history is preserved, and a new follow-up is created.

## 10. Test list

- **Unit:** serial allocation is gapless and per-notary-per-year; cancelled
  entries keep their serial; attestation refuses an unapproved source; clause
  selection refuses an unmatched condition set; jurisdiction snapshot is not
  re-read; back-dating requires a reason.
- **Contract:** `instrument.attested` payload carries both jurisdictions, the
  regime, and the notary — and no party names; register entry schema returns
  references only; monthly period schema.
- **Integration:** approve → export → attest writes attestation, register entry,
  protocol, audit and outbox atomically; `instrument.attested` produces the
  correct awaiting-confirmation registration deadline for each of the deed
  30-day, deed 60-day, and RTA seven-working-day branches; month close produces
  exactly one period and is idempotent on replay; a nil month still produces a
  period and an obligation.
- **Security:** cross-organisation register read denied; a non-notary cannot
  attest; an expired certificate cannot attest; register rows contain no
  identity values; 404 for a non-member on the matter-scoped routes.

## 11. Decisions to confirm before coding

1. The register is notary-scoped with a gapless per-year serial, allocated in
   the attestation transaction.
2. Attestation requires an approved and exported instrument, pinning its content
   hash; external paper instruments need a recorded reason.
3. Practising jurisdiction is snapshotted at attestation.
4. Every executant needs `verified` identity evidence.
5. Monthly periods are generated by the scheduler, including nil returns.
6. Attestations are immutable; corrections are new instruments plus a recorded
   cancellation.
7. Form F and Form E prescribed content stays `legal-content-blocked` in
   `content-governance-service` until a lawyer supplies it — this service can be
   built and tested against structure without that wording, but it cannot
   produce a submittable return.
