# retention_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md` §10,
`obligations-service.md` §10, `infrastructure.md`, `party-service.md`,
`notarial-register-service.md`, `audit-service.md`, and `events.md`.

This service was missing. `obligations-service.md` §10 defines `RetentionPolicy`
and `LegalHold`, states that "the retention engine prevents deletion", and then
explicitly disclaims owning record destruction. `infrastructure.md` mentions
separate retention prefixes. The plan defers retention to §12. So nothing owned
it — and `retention.hold-placed` and `retention.hold-released` had a consumer and
no publisher.

With PDPA 2022 on one side and the FIU six-year record-keeping rule on the
other, "we will decide later" is itself a compliance position. This service
makes the position explicit and, importantly, makes deletion *hard* by default.

## 1. What it owns

- **RetentionPolicy** versions: which record class is kept, for how long, from
  which trigger, under which authority.
- **LegalHold**: an override that prevents destruction regardless of policy.
- **RetentionSchedule**: the computed disposition date for a concrete record
  set, and its current disposition state.
- The **destruction workflow**: proposal, human approval, execution, and the
  non-content tombstone that survives it.
- **Erasure requests** under PDPA, and the lawful-basis assessment that decides
  whether one can be honoured.

It does **not** own the records themselves. It never reaches into another
service's tables. It publishes a decision; the owning service executes it
through its own port and reports back.

```text
retention_service   decides what may be destroyed and when
owning service      executes the destruction of its own records
audit_service       keeps the tombstone forever
```

## 2. Default posture: nothing is deleted

Draftly's default is **retain**. Every destruction requires all four of:

1. a matured `RetentionSchedule` under an `approved` policy version;
2. no active `LegalHold` covering the record scope;
3. an explicit human approval carrying `retention.approve-destruction`;
4. a tombstone written before the bytes go.

A schedule maturing does not destroy anything. It creates a `retention-review`
obligation for a human (`obligations-service.md` §10). Automatic deletion on a
timer is not implemented in V0 and is not a configuration option.

## 3. Where it sits

```text
GET  /api/v1/retention/policies
POST /api/v1/retention/policies                (maintainer; versioned)
GET  /api/v1/retention/schedules
GET  /api/v1/retention/holds
POST /api/v1/retention/holds
POST /api/v1/retention/holds/{id}/release
POST /api/v1/retention/dispositions/{id}/approve
GET  /api/v1/retention/erasure-requests
POST /api/v1/retention/erasure-requests
              |
              v
      api/v1/retention.py
              |
              v
 application/retention_service.py
              |
              +--> RetentionPolicyRepository
              +--> RetentionScheduleRepository
              +--> LegalHoldRepository
              +--> RecordScopeResolverPort
              +--> DestructionCommandPort   (per owning service)
              +--> EventPort / AuditPort
```

## 4. Domain models

### 4.1 RecordClass and RecordScope

```text
RecordClass =
  matter-file | evidence-original | evidence-derivative | verified-record |
  draft | approved-export | notarial-protocol | notarial-register |
  party-identity | screening-record | cdd-record | voice-capture |
  transcript | session-memory | notification-delivery | billing-record |
  audit-event | research-answer
```

```text
RecordScope
  organisationId
  recordClass
  selector           # matterId | partyId | notaryUserId | exportId | ...
  selectorKind
```

A scope is a stable description of a record set, not a list of primary keys, so
a hold placed today still covers rows created tomorrow inside that scope.

### 4.2 RetentionPolicy

```text
RetentionPolicy
  id
  recordClass
  jurisdiction
  triggerEvent           # matter.closed | instrument.attested | party last activity | ...
  retentionPeriod        # ISO-8601 duration
  minimumPeriod?
  authority
  sourceUrl
  sourceSection
  effectiveFrom
  effectiveTo?
  approvalState = draft | approved | retired
  approvedBy?
  approvedAt?
  version
```

Policies are **governed content**: `content_governance_service` owns the
`draft → approved → retired` lifecycle and the immutable versions, exactly as it
does for deadline rules (`content-governance-service.md` §7). This service reads
approved versions, pins the selected version on each schedule, and evaluates it.

Changing an approved policy never silently re-dates an existing schedule.
Migration is an explicit, audited recalculation.

### 4.3 RetentionSchedule

```text
RetentionSchedule
  id
  organisationId
  recordScope
  policyId
  policyVersion
  triggerEventId
  triggerAt
  disposeAfter
  state = accruing | matured | review-requested | disposition-approved |
          destroyed | held | exempt
  activeHoldIds
  reviewObligationId?
  destructionApprovedBy?
  destructionApprovedAt?
  destroyedAt?
  tombstoneId?
  version
```

### 4.4 LegalHold

```text
LegalHold
  id
  organisationId
  recordScope
  reason
  sourceAuthority        # court order | regulator | investigation | internal
  placedBy
  placedAt
  expectedReviewOn?
  releasedBy?
  releasedAt?
  releaseEvidenceRef?
  state = active | released
```

A hold is scope-based and **wins over everything**. While a hold is active the
covered schedules are `held`, no disposition can be approved, and no merge,
purge, or provider-side deletion may run.

### 4.5 Tombstone

```text
Tombstone
  id
  organisationId
  recordScope
  recordCount
  policyId
  policyVersion
  approvedBy
  destroyedAt
  checksumManifestRef    # checksums of what was destroyed, not the content
  method = hard-delete | crypto-erase | anonymise
```

The tombstone is an audit record and is itself never destroyed. After
destruction the system can still answer "a record of this class existed for this
matter and was destroyed on this date under this authority" — which is what a
regulator asks — without retaining the content.

## 5. Methods

### evaluate_schedules(as_of) — scheduled, daily

Runs as `retention.evaluate` (`jobs-and-workers.md` §6):

1. For each approved policy, resolve the record scopes whose trigger event has
   occurred.
2. Create or update a `RetentionSchedule` pinning the policy version.
3. Move matured schedules to `matured`, unless a hold covers them, in which case
   `held`.
4. Publish `retention.review-due` for newly matured schedules;
   `obligations_service` creates the `retention-review` obligation.

Idempotent on `(recordScope, policyId, policyVersion)`.

### place_hold(ctx, scope, reason, authority) -> LegalHoldRead

Requires `retention.hold`. Takes effect immediately: covered schedules move to
`held` and any pending disposition approval is revoked. Publishes
`retention.hold-placed`, which `document_service`, `export_service`, and
`party_service` consume to refuse destruction, merge, and expiry cleanup.

A hold may be placed on a scope with no current records. That is the point — an
anticipated investigation is held before the next document arrives.

### release_hold(ctx, hold_id, evidence_ref) -> LegalHoldRead

Requires `retention.release` and a recorded release evidence reference.
Publishes `retention.hold-released`. Covered schedules recompute; a schedule
already past its date becomes `matured`, not `destroyed`.

### approve_disposition(ctx, schedule_id, method) -> RetentionScheduleRead

Requires `retention.approve-destruction`. Re-checks holds at approval time and
again at execution time. Writes the tombstone first, then calls
`DestructionCommandPort` on the owning service, then marks `destroyed`.
Publishes `retention.destruction-approved`.

If the owning service reports partial failure, the schedule stays
`disposition-approved` with the failure recorded; it never reports `destroyed`
for records that still exist.

### create_erasure_request(ctx, subject_ref) -> ErasureRequestRead

A PDPA data-subject erasure request. It is **assessed, not executed**: legal and
professional retention duties usually override erasure for matter records. The
assessment records which record classes can be erased (typically marketing and
optional contact data), which cannot and why (statutory retention, legal hold,
professional obligation), and the response sent to the subject. Nothing is
deleted without the same four-condition gate in §2.

## 6. Interaction with other services

| Service | Contract |
| --- | --- |
| `document_service` | Consumes `retention.hold-placed/released`; refuses orphan-blob collection and any deletion inside a held scope; implements `DestructionCommandPort` for originals and derivatives separately |
| `export_service` | Approved exports have their own retention class; expiry of a signed URL is not destruction |
| `party_service` | Refuses merge and identifier purge inside a held scope; supports `crypto-erase` of `identifierValue` as a destruction method |
| `notarial_register_service` | Protocol and register records carry long statutory retention; destruction is effectively never in V0 |
| `voice_service` | Audio and transcripts are separately classed; confirmed-transcript retention must preserve anything needed to explain a downstream matter action (`voice-service.md` §10) |
| `memory_service` | Session memory is a cache; it is purged on scope destruction and rebuilt from surviving authoritative stores if the scope survives |
| `audit_service` | Audit events are the one class this service cannot propose for destruction in V0. Tombstones are audit records |
| `obligations_service` | Receives `retention.review-due` and creates the human review obligation |

## 7. Invariants

| Invariant | Enforcement |
| --- | --- |
| Nothing is destroyed automatically | Maturity creates a review obligation; destruction needs explicit human approval |
| A legal hold beats every policy | Hold state is re-checked at approval and again at execution; a held scope cannot be disposed |
| Retention policies are governed | Approved versions only, pinned per schedule, from `content_governance_service` |
| Policy change never re-dates silently | Existing schedules keep their pinned version; migration is explicit and audited |
| Destruction leaves a tombstone | Tombstone written before bytes are removed; tombstones are never destroyed |
| This service never touches other tables | Destruction runs through `DestructionCommandPort` on the owning service |
| Erasure is assessed against duties | A PDPA request cannot override statutory or professional retention |
| Partial failure is not success | A schedule stays `disposition-approved` until every owning service confirms |
| Audit survives | Audit events are outside V0 destruction scope |
| Every action audited | Place, release, approve, execute, and assess all write audit events |

## 8. Failure modes

- Hold placed while a disposition is mid-flight — approval is revoked; if
  execution already started, the owning service aborts on its own hold check and
  reports partial failure.
- Hold released after the retention date has passed — schedule becomes
  `matured`, not `destroyed`; the human review still happens.
- A record scope spans two organisations — rejected at scope construction; a
  scope is always organisation-bounded.
- Policy retired while schedules reference it — schedules keep the pinned
  version; new schedules use the successor.
- Owning service reports more records destroyed than the tombstone counted —
  logged as a reconciliation error and alerted; the count discrepancy is not
  silently accepted.
- Backup restore reinstates destroyed records — the tombstone is the detector:
  a restore is followed by a mandatory tombstone reconciliation sweep before the
  environment is returned to service (`infrastructure.md` §9).

## 9. Test list

- **Unit:** maturity computation from trigger and period; hold precedence at
  both approval and execution; tombstone written before destruction; erasure
  assessment blocks on a statutory class; policy version pinning survives a
  policy change.
- **Contract:** `retention.hold-placed/released/review-due/destruction-approved`
  payloads match the registry; policy and schedule schemas; the
  `DestructionCommandPort` contract each owning service implements.
- **Integration:** matter closure creates a schedule; maturity creates one
  obligation and is idempotent on replay; a hold blocks orphan collection in
  `document_service` and merge in `party_service`; approved disposition
  destroys through the owning service and records the tombstone; partial failure
  does not mark `destroyed`; restore-then-reconcile detects reinstated records.
- **Security:** only `retention.hold` / `retention.release` /
  `retention.approve-destruction` holders can act; cross-organisation scopes
  rejected; tombstones contain no record content; a destroyed scope leaves no
  readable residue in derivatives, memory, or search indexes.

## 10. Decisions to confirm before coding

1. Retain by default; no automatic timer-based destruction in V0.
2. Legal hold is scope-based and overrides every policy.
3. Retention policies are governed content with pinned versions.
4. Tombstones are permanent and are audit records.
5. Audit events are out of destruction scope for V0.
6. `crypto-erase` is an acceptable destruction method for encrypted identifiers,
   subject to key-destruction evidence.
7. The concrete retention periods per record class are a **legal review item**.
   This service ships with the mechanism and an empty approved-policy set; it
   must not invent a period. The FIU six-year rule and any Notaries Ordinance
   protocol duty are the first two policies to draft
   (`obligations-service.md` §24).
