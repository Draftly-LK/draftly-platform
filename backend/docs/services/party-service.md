# party_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`, `matter-service.md`,
`verification-service.md`, `obligations-service.md`, `retention-service.md`,
`security-model.md`, and `events.md`.

This service was missing. `matter-service.md` §4.3 stores a
`MatterPartyReference.partyRecordId` and defers identity data to "the protected
party or verified-record tier" — a tier no document described. Nothing owned
party records, NIC and passport evidence, beneficial ownership, CDD evidence,
or screening results, even though AML customer due diligence is a workflow gate
and NIC identity checking at attestation is a named RTA requirement
(`auth-service.md` §3, "NIC / identity — keep two things distinct").

It is the highest-PII store in the product, so it gets its own boundary, its own
capability set, and its own retention rule.

## 1. What it owns

The **protected identity tier**: a Party record per real-world person or entity
known to an organisation, the identity evidence that supports it, beneficial
ownership, the CDD risk assessment, and screening outcomes. It owns the link
between a Party and the matters it appears in, and the role it plays in each.

It does **not** own:

- the matter's transaction-role association (`matter_service` owns
  `MatterPartyReference`);
- verified matter particulars such as a transferee name as it appears on a deed
  (`verification_service` owns those, with source spans);
- the workflow gate that requires CDD (`task_service`);
- the dated obligation created when identity evidence expires
  (`obligations_service`);
- login identity (`auth_service` — a party is a subject of a matter, not a user
  of the system);
- deletion (`retention_service`).

### The three "identity" concepts, kept apart

Conflating these would put matter PII on the auth path, which is exactly what
`auth-service.md` §3 warns against:

```text
auth_service        who is using Draftly            User + UserIdentity
party_service       who the matter is about         Party + IdentityEvidence
verification_service what a document says about them VerifiedFact + EvidenceSpan
```

A party's NIC lives here as an identity attribute with its evidence. The NIC
*as read off a deed* is a candidate particular in `verification_service`.
Reconciling the two is a `check_service` rule (`identity` category), not a
silent overwrite in either direction.

## 2. Where it sits

```text
GET   /api/v1/parties                       (organisation-scoped search)
POST  /api/v1/parties
GET   /api/v1/parties/{id}
PATCH /api/v1/parties/{id}
POST  /api/v1/parties/{id}/identity-evidence
POST  /api/v1/parties/{id}/beneficial-owners
POST  /api/v1/parties/{id}/cdd
POST  /api/v1/parties/{id}/screening
GET   /api/v1/matters/{id}/parties
              |
              v
      api/v1/parties.py
              |
              v
 application/party_service.py
              |
              +--> PartyRepository
              +--> IdentityEvidenceRepository
              +--> ScreeningPort
              +--> DocumentReadPort
              +--> EventPort / AuditPort
```

The router authenticates and parses only. The service takes a
`RequestContext` and enforces organisation scope before anything else
(`security-model.md` §2). It imports no FastAPI, no SQLAlchemy, and no screening
provider SDK.

## 3. Domain models

### 3.1 Party

```text
Party
  id
  organisationId
  partyKind = natural-person | company | partnership | trust |
              statutory-body | other
  displayName
  nameParts
  formerNames
  dateOfBirth?
  registrationNumber?          # company/BR number for non-natural persons
  nationality?
  residencyStatus?
  addresses
  contactPoints
  riskRating = unassessed | low | standard | high
  screeningStatus = not-run | clear | potential-match | confirmed-match
  confidentialityLevel
  mergedIntoPartyId?
  version
  createdAt
  updatedAt
```

`displayName` and `nameParts` are stored separately because Sri Lankan names do
not reliably split into given/family, and the deed spelling, the NIC spelling,
and the survey-plan spelling frequently differ. All three are kept; none is
normalised away. Comparison is a `check_service` concern with a recorded
normalisation (`check-service.md` open decision 4).

### 3.2 IdentityEvidence

```text
IdentityEvidence
  id
  partyId
  evidenceKind = nic | passport | driving-licence | birth-certificate |
                 company-registration | board-resolution |
                 power-of-attorney | utility-bill | other
  identifierValue                # encrypted at rest
  identifierLast4                # for display and search
  issuedOn?
  expiresOn?
  issuingAuthority?
  documentId?
  documentVersionId?
  evidenceSpan?
  verifiedBy?
  verifiedAt?
  state = recorded | verified | rejected | expired | superseded
  supersedesEvidenceId?
  version
```

Rules:

- `identifierValue` is encrypted at rest with a separate key from ordinary
  matter data, and is **never** returned by a list endpoint. Lists return
  `identifierLast4`.
- Where the evidence came from an uploaded document, `documentVersionId` pins
  the immutable version and `evidenceSpan` pins the region, exactly as a
  verified particular does (invariant 1). Identity evidence with no document is
  allowed only for a `recorded` state; it cannot reach `verified`.
- Evidence is append-only. A renewed NIC or passport creates a successor with
  `supersedesEvidenceId`; the predecessor stays queryable.
- `expiresOn` drives `party.identity-document-expiry-recorded`, which
  `obligations_service` turns into a dated follow-up (`events.md` §5.3).

### 3.3 BeneficialOwner

```text
BeneficialOwner
  id
  partyId                        # the entity
  ownerPartyId                   # the natural person behind it
  ownershipKind = shareholding | voting-rights | control-other | senior-managing
  percentage?
  evidenceRefs
  determinedBy
  determinedAt
  state = recorded | verified | superseded
```

Beneficial ownership is a graph, not a field. A company party may resolve to
several natural-person parties, each itself a Party record with its own identity
evidence. Cycles are rejected at write time.

### 3.4 CddAssessment

```text
CddAssessment
  id
  partyId
  matterId?                      # null for organisation-level KYC
  level = standard | simplified | enhanced
  riskFactors
  outcome = pending | complete | blocked
  assessedBy
  assessedAt
  reviewDueOn?
  policyVersion
  version
```

`policyVersion` pins the approved CDD policy the assessment ran under, so a
later policy change does not retroactively invalidate or silently re-grade a
completed assessment. `reviewDueOn` produces a dated obligation.

### 3.5 ScreeningResult

```text
ScreeningResult
  id
  partyId
  listVersion
  providerRef
  outcome = clear | potential-match | confirmed-match
  matchCount
  reviewedBy?
  reviewedAt?
  dispositionReason?
  confidentialityLevel = restricted-compliance
  createdAt
```

Screening results are **always** `restricted-compliance`. The matched list
entry, the narrative, and the provider payload are stored in a separate
restricted table reachable only with `compliance.view`, never joined into an
ordinary party read.

### 3.6 Confidentiality

```text
ConfidentialityLevel = standard | private-matter | restricted-compliance
```

Same enum as `obligations-service.md` §5.4, deliberately. A party's
`confidentialityLevel` is the maximum of its own setting and any restricted
screening outcome attached to it.

## 4. Ports

- `PartyRepository` — persist and load parties; organisation-scoped queries
  only; optimistic concurrency.
- `IdentityEvidenceRepository` — append-only evidence, beneficial owners, CDD
  assessments; field-level encryption for `identifierValue`.
- `ScreeningPort` — `screen(party_snapshot, list_version) -> ScreeningResult`.
  Provider-neutral. V0 may implement it as a manual-entry adapter where a
  compliance officer records an externally run result; the domain contract is
  identical either way.
- `DocumentReadPort` — resolve a `documentVersionId` to a readable, matter-scoped
  version so evidence can be pinned. This service never signs URLs.
- `EventPort`, `AuditPort` — as every service.

## 5. Methods

### create_party(ctx, input) -> PartyRead

Requires `party.record-identity`. Organisation-scoped. Runs the duplicate probe
(§7) and returns candidate matches rather than silently merging. Audits
`party.created` with no identifier value.

### record_identity_evidence(ctx, party_id, evidence) -> IdentityEvidenceRead

Requires `party.record-identity`. Encrypts `identifierValue`, stores
`identifierLast4`, pins `documentVersionId` and `evidenceSpan` where supplied,
and sets `state = recorded`. Moving to `verified` additionally requires a
practising notary (`security-model.md` §3.3) and a pinned document version —
identity evidence cannot be verified against nothing.

Publishes `party.identity-evidence-recorded`, and
`party.identity-document-expiry-recorded` when `expiresOn` is present.

### record_beneficial_owner(ctx, party_id, owner) -> BeneficialOwnerRead

Requires `party.record-identity`. Rejects a cycle and rejects an owner party in
another organisation.

### complete_cdd(ctx, party_id, assessment) -> CddAssessmentRead

Requires `party.record-identity`. Pins the approved CDD policy version. The
assessment is an input to a `task_service` gate; this service does not decide
whether the matter may proceed.

### record_screening(ctx, party_id, result) -> ScreeningResultRead

Requires `compliance.act`. A `confirmed-match` publishes
`party.designated-person-confirmed`, which is the trigger for the restricted
24-hour escalation in `obligations-service.md` §8.2. The event carries the party
id, the organisation, and the confidentiality level — no name, no list entry, no
narrative (`events.md` §2).

### get_party(ctx, party_id) -> PartyRead

Organisation-scoped. Returns `identifierLast4`, never a full identifier, unless
the caller holds `party.read-identity` **and** the request names a lawful
purpose that is recorded in the access audit event (§8).

### list_matter_parties(ctx, matter_id) -> MatterPartyRead[]

Joins `matter_service`'s `MatterPartyReference` to the party records the caller
may see. A caller who is not a matter member gets 404.

### merge_parties(ctx, source_id, target_id, reason) -> PartyRead

Requires `administrator`. Sets `mergedIntoPartyId` on the source; never deletes.
All evidence, ownership, assessments, and matter links repoint to the target,
and the merge is reversible from the audit trail.

## 6. Entitlement and metering

Party records are not separately metered in V0. `ScreeningPort` calls are:
`require_feature(org, "screening.enabled")` then
`reserve_usage(org, "screening_checks.monthly", 1, operation_id=screening_id)`,
consumed on a provider response and released on terminal failure
(`billing-service.md` §7.2).

## 7. Duplicate detection, not automatic merging

The same person appears across matters. Draftly surfaces candidates and lets a
human decide:

```text
probe = exact identifier match (encrypted equality)
      | normalised name + date of birth
      | normalised name + shared address
      | registration number for an entity
```

An exact identifier match is a strong candidate and still not an automatic
merge. Merging identity records on a fuzzy name match is how the wrong person
ends up on a deed.

## 8. Access to identity values is itself audited

Reading a full NIC or passport number is a privileged read, not a side effect of
opening a screen. Every call that returns a decrypted `identifierValue` writes
an audit event with `targetType: "party"`, the purpose supplied by the caller,
and the fields returned. This is the one place in Draftly where a *read* is
audited, and it is deliberate.

## 9. Invariants

| Invariant | Enforcement |
| --- | --- |
| Party data is organisation-scoped | Every query filters `ctx.organisationId` first; a cross-organisation read is a 404 |
| Identifiers are encrypted and rarely returned | `identifierValue` encrypted at rest, excluded from lists, decryption audited with a purpose |
| Verified evidence has a pinned source | `verified` requires `documentVersionId` and an `evidenceSpan` on an immutable version (inv. 1) |
| Evidence is append-only | Renewal supersedes; nothing is overwritten or deleted (inv. 7 pattern) |
| Auth identity is not party identity | No `UserIdentity` field is readable here and no party record grants access |
| Screening detail is restricted | `restricted-compliance` allowlist; match detail in a separate table; never in events, logs, or notifications |
| Merges preserve history | `mergedIntoPartyId` pointer, never a delete |
| CDD pins its policy version | A later policy change cannot silently re-grade a completed assessment |
| No automatic identity merge | Candidates are surfaced; a human with `administrator` decides |
| Every mutation audited | `AuditPort.record` with `targetType: "party"`, no identifier values in the payload |

## 10. Failure modes

- Two matters in the same organisation reference the same real person under
  different spellings — duplicate probe surfaces both, neither is merged
  automatically, and a `check_service` identity finding flags the mismatch.
- An identity document expires mid-matter — evidence moves to `expired`, the
  dependent CDD assessment is marked stale, and the obligation fires. The matter
  is not silently blocked without a visible reason.
- A screening provider is unavailable — the screening stays `not-run`, the CDD
  gate stays incomplete, and nothing infers `clear`.
- A `confirmed-match` is recorded — the party is restricted immediately, the
  restricted escalation obligation is created, and ordinary matter members lose
  visibility of the screening detail without being told why.
- A party is referenced by a closed matter under legal hold — merge and any
  future destruction are refused by `retention_service`.
- A deed reads a different NIC than the party record holds — this is a
  cross-document finding, not an update. Neither record wins silently.

## 11. Test list

- **Unit:** evidence state machine including supersession; `verified` requires a
  pinned document version; beneficial-owner cycle rejection; confidentiality is
  the maximum of party and screening; duplicate probe returns candidates and
  never merges.
- **Contract:** party list and detail schemas return `identifierLast4` and never
  `identifierValue`; the screening event payload contains no name, list entry,
  or narrative; `party.identity-document-expiry-recorded` matches the registry.
- **Integration:** record NIC evidence pinned to a document version; expiry
  produces an obligation; confirmed match produces the restricted escalation and
  hides detail from an ordinary member; merge repoints every dependent record;
  legal hold blocks merge.
- **Security:** cross-organisation party read denied; a member without
  `party.read-identity` never receives a full identifier; every decryption is
  audited with a purpose; no identifier appears in logs, events, or error
  bodies; compliance-restricted rows return no existence signal.
- **Privacy:** encryption at rest verified for `identifierValue`; a database
  dump of the party tables contains no plaintext identifier.

## 12. Decisions to confirm before coding

1. Party is organisation-scoped, not matter-scoped, so one person is one record
   across a firm's matters.
2. Identity evidence is append-only and pins an immutable document version to
   reach `verified`.
3. Screening results are always `restricted-compliance` with match detail in a
   separate table.
4. Reading a full identifier is audited with a caller-supplied purpose.
5. `ScreeningPort` may be a manual-entry adapter for V0; the domain contract
   does not change when a provider is added.
6. Merge is `administrator`-only, pointer-based, and reversible.
7. Encryption key for `identifierValue` is separate from the general database
   key and is rotatable — confirm the key-management approach with
   `infrastructure.md` §7.
