# check-service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`verification-service.md`, `document-service.md`, and `document-processing.md`.
This service is the **deterministic consistency engine** over the verified
record — the mentor's rule that *everything must tally*. It runs versioned rules
and cross-document reconciliations, never generated prose.

Maps to plan **Phase 5** (checks and guided tasks), API rows **Findings** (§7),
and the trust-boundary row *Verified matter record* (§5.2, read side).

## 1. What it owns

Running **versioned, authority-tagged rules** over the verified/corrected matter
record and producing **findings** — a `pass`, `warning`, `fail`, or
`needs-review` per rule, each pointing at the facts it touched and the evidence
those facts hang on. It owns the cross-document reconciliation (the deed schedule
against the survey plan against the municipal assessment) that surfaces the
red-flag mismatches, and it owns the resolution trail for each finding.

It does **not** verify facts (`verification_service` does), does **not** write
prose or suggestions in natural language (only i18n keys), and does **not**
approve anything. It reads the verified record and reports; the check engine is
deterministic and contains no model call.

## 2. Where it sits

```text
GET  /api/matters/{id}/checks                       ─┐
GET  /api/matters/{id}/cross-checks                 ─┼─→ api/v1/checks.py ─→ application/check_service.py
POST /api/matters/{id}/checks/{checkId}/resolve     ─┘                              │
                                                                                    │ orchestrates
verification_service (verified/corrected facts) ──(read)───────────────────────────▶│
                                                                                    ▼
                                            ports: RuleCatalogPort, ParticularReadPort,
                                                   CheckRepository, AuditPort
```

The router authenticates and parses only. The service takes an authenticated
`RequestContext` and orchestrates domain plus ports. It imports no SQLAlchemy, no
FastAPI, and — the load-bearing rule — **no model SDK**: the engine is pure
domain logic over data. Evidence is carried as spans, resolved to page images
through `document_service`, never as raw storage paths.

## 3. Domain models it needs

In `domain/findings.py`, mirroring the frontend contract
(`frontend/src/types/check.ts`) field for field:

- **Check** — `id`, `matterId`, `category: CheckCategory`, `descriptionKey`,
  `status: CheckStatus`, `affectedFactIds: string[]`, `evidence: EvidenceSpan[]`,
  `authority?: Authority`, `suggestedResolutionKey`, `ownerId?`,
  `resolution?: CheckResolution`. One finding from one rule against the record.
- **CheckResolution** — `action: resolved | waived | document-requested |
  checklist-created`, `reason`, `actorId`, `timestamp`. The disposition trail.
- **CrossCheck** — `id`, `matterId`, `labelKey`, `bindings: CrossCheckBinding[]`,
  `verdict: match | mismatch | incomplete`, `checkId`. One
  reconciliation across documents, linked to its `Check`.
- **CrossCheckBinding** — `factId`, `evidence: EvidenceSpan`. One participant in
  the reconciliation, grounded in the exact span it was read from.

`CheckStatus = pass | warning | fail | needs-review`.
`CheckCategory = missing-document | identity | parcel | chain-of-title |
registration | stamp-duty | execution | jurisdiction`.

`descriptionKey` and `suggestedResolutionKey` are **i18n keys, not generated
text** — the engine selects a key, it never writes a sentence. This is how the
"keep prose out of the check engine" rule (Phase 5) is enforced in the type
itself.

The `Authority` on a `Check` (`frontend/src/types/answer.ts`: `id`, `title`,
`reference`, `type`, `courtLevel`, `weight`, `verified`) carries the rule's legal
basis so a finding says which statute, gazette, or practice direction it applies.

## 4. Ports it depends on

In `ports/`:

- `RuleCatalogPort` — load the active, versioned rule definitions with their
  applicability conditions, authority metadata, version, and effective date. The
  catalogue is a **backend addition** (§7, open decision) — the frontend has no
  standalone rule type.
- `ParticularReadPort` — read `verified`/`corrected` facts for a matter, backed
  by `verification_service`. The engine reads only accepted facts; an `unreviewed`
  or `blocked` fact is not check input.
- `CheckRepository` — persist and load `Check` and `CrossCheck`, append a
  `CheckResolution`, matter-scoped queries only.
- `AuditPort` — `record(event)`; every resolution and override is audited
  (invariant 8).

## 5. The methods

### run_checks(ctx, matter_id) -> CheckRead[]

Deterministic evaluation.

1. Re-check matter membership; 404-not-403 for a non-member (Phase 2 exit gate).
2. Load the active rules from `RuleCatalogPort` at their pinned versions.
3. For each rule whose applicability condition matches the matter, read the
   required `verified`/`corrected` facts through `ParticularReadPort` and evaluate
   the rule as pure logic.
4. Produce a `Check`: `status` from the rule outcome, `affectedFactIds` for every
   fact it read, `evidence` gathered from those facts' `EvidenceSpan`s (so the
   finding inherits provenance tied to immutable `DocumentVersion`s),
   `authority` from the rule, `descriptionKey` and `suggestedResolutionKey` as
   keys.
5. A rule that cannot run because a required fact is missing or `blocked` yields
   `needs-review`, not a silent `pass` — an abstention, recorded as such.

`get_checks` returns the persisted findings; a re-run recomputes them and is a
no-op where nothing changed. Findings recompute when a fact is corrected, so the
record and its checks never drift apart.

### list_cross_checks(ctx, matter_id) -> CrossCheckRead[]

The *everything must tally* engine. A `CrossCheck` reconciles the same real-world
particular as read from **different documents** — the deed schedule, the survey
plan, and the municipal assessment — and reports whether they agree:

- Each `CrossCheckBinding` names the `factId` and the `EvidenceSpan` it was read
  from, so every side of the comparison is grounded in a specific spot on a
  specific document version. A mismatch always shows *which* documents disagree
  and where.
- `verdict = match` when the bound values agree, `mismatch` when they conflict
  (the red flag), `incomplete` when a required document or fact is not yet in the
  record.
- Each `CrossCheck` links to a `Check` (`checkId`) so a mismatch carries a status,
  a category (`parcel`, `chain-of-title`, `identity`), and a resolution path like
  any other finding.

The binding-to-evidence rule is the point: the engine never asserts a mismatch it
cannot show. Provenance on both sides is what makes the red flag actionable.

### resolve_check(ctx, matter_id, check_id, action, reason) -> CheckRead

1. Role gate: resolving a finding is a lawyer decision (invariant 3).
2. Record a `CheckResolution{ action, reason, actorId: actor, timestamp: now }`.
   `action` is one of `resolved`, `waived`, `document-requested`,
   `checklist-created` — a `waived` finding is explicitly waived by a named
   lawyer with a reason, not silently cleared.
3. Set `ownerId` and persist. The finding's `status` is not rewritten by a
   resolution — a `waived` `fail` is still a `fail` with a recorded waiver, so the
   distinctness of `pass`/`warning`/`fail`/`needs-review` survives (Phase 5 exit
   gate).
4. Audit `finding.resolved` (or `finding.waived`) with actor, target, and reason
   (invariant 8).

## 6. The blocking seam to approval

An **unresolved blocker prevents approval**. `check_service` does not approve —
it exposes the blocking set, and `approval_service` refuses to approve a draft
while that set is non-empty (Phase 5 exit gate; plan §7 Approval: "blockers").
Naming the seam here fixes the enforcement point.

A finding is a **blocker** when its `status` is `fail` or `needs-review` and it
has no `resolution` with `action = resolved` or `waived`. A `warning` is advisory
and does not block. A `document-requested` or `checklist-created` resolution
tracks follow-up but does **not** clear a blocker — only `resolved` or `waived`
does. This keeps the mentor's rule enforceable: the draft cannot be approved
until every red flag is either fixed or a lawyer has waived it on the record.

## 7. Invariants and rules this service enforces

| Invariant / rule | How |
| --- | --- |
| Deterministic only (Phase 5) | The engine is pure domain logic; no model SDK imported; `descriptionKey`/`suggestedResolutionKey` are i18n keys, never generated text |
| Runs only over accepted facts | `ParticularReadPort` returns `verified`/`corrected` facts; `unreviewed`/`blocked` are not check input |
| Every active rule is governed | `RuleCatalogPort` supplies authority, version, effective date, and tests per rule (Phase 5 exit gate) |
| Status distinctness kept | `pass`/`warning`/`fail`/`needs-review` are stored as computed; a resolution never rewrites the status |
| Unresolved blockers prevent approval | `fail`/`needs-review` without a `resolved`/`waived` resolution block; the seam to `approval_service` (§6) |
| Findings inherit provenance | `Check.evidence` and every `CrossCheckBinding.evidence` come from the facts' spans, tied to immutable `DocumentVersion`s (invariant 1) |
| Every resolution audited (inv. 8) | `AuditPort.record` on resolve, waive, and override, with reason |
| Matter isolation | Membership re-checked; 404 hides existence |

## 8. Failure modes to handle explicitly

- **A rule references a fact not yet verified** — `needs-review` (abstention),
  not a false `pass`; it recomputes to a real status once the fact is accepted.
- **A fact a finding depends on is corrected** — the finding recomputes; a
  resolution attached to the stale evaluation is superseded, not silently kept.
- **Cross-check missing one document** — `verdict = incomplete`, not `match`; the
  gap is visible, not hidden as agreement.
- **Rule catalogue version bumped mid-matter** — findings record the rule version
  they ran under; a re-run under a new version is a new evaluation, and the change
  is traceable.
- **Waived blocker re-triggered by new evidence** — a superseding document or a
  correction reopens the finding; the prior waiver stays in history.

## 9. Phase 5 exit gates and how they are met

- **Each active rule has authority, version, effective date, and tests** —
  `RuleCatalogPort` carries all four; a rule without them is not loaded.
- **`pass`/`warning`/`fail`/`needs-review` stay distinct** — computed and stored
  separately; resolutions annotate, never overwrite (§5, §7).
- **Unresolved blockers prevent approval** — the blocking-set seam to
  `approval_service` (§6).
- **Lawyer-labelled evaluation reports precision, recall, abstentions** — the
  evaluation layer runs the catalogue against a labelled matter set and scores
  findings against lawyer labels, counting `needs-review` as abstentions (§10).

## 10. Test list

- **Unit:** each rule's pass/warning/fail/needs-review outcome on fixture facts;
  applicability gating; a missing required fact yields `needs-review` not `pass`;
  cross-check `match`/`mismatch`/`incomplete` verdicts; a resolution does not
  rewrite `status`; blocker classification (which findings block approval).
- **Contract:** `checks`, `cross-checks`, and `resolve` response schemas match
  `Check`/`CrossCheck`/`CheckResolution`; the `RuleCatalogPort` rule-definition
  schema (authority, version, effective date).
- **Integration:** run the catalogue over a verified record in real PostgreSQL;
  correcting a fact recomputes the dependent findings; a `fail` finding blocks
  `approval_service` until `resolved`/`waived`; cross-check surfaces a
  deed-schedule-versus-survey-plan mismatch with both spans.
- **Security:** cross-matter check read and resolve denied; 404-not-403;
  a clerk cannot resolve or waive; no raw client value in logs.
- **Evaluation:** on a lawyer-labelled matter set, report precision, recall, and
  abstention rate per rule category, to tune rule thresholds and the review
  expectation.

## 11. Open decisions

Recommended defaults in bold; confirm or override before coding.

1. **The rule catalogue is a backend addition** — the frontend has no standalone
   `Rule` or `Severity` type: `CheckStatus` doubles as severity, and the closest
   existing shape is `StepRule` in the workflow types. The plan (Phase 5) wants
   "versioned rule definitions". Lean **a backend `RuleDefinition` behind
   `RuleCatalogPort`** — `id`, `category`, `version`, `effectiveDate`,
   `authority`, applicability condition, and the deterministic predicate — with a
   migration and tests per rule. It is not exposed as a frontend type; the
   frontend sees only the `Check` a rule produces.
2. **Rule authoring format** — code predicates, a declarative rule table, or a
   small DSL? Lean **typed Python predicates in `domain/findings` for V0**
   (testable, no interpreter to build), with each rule pinned to a catalogue
   version; revisit a data-driven format once the rule set is stable.
3. **Which statuses block approval** — `fail` clearly blocks; does
   `needs-review`? Lean **both `fail` and `needs-review` block** (an unresolved
   abstention is not safe to approve past); `warning` is advisory.
4. **Cross-check tolerance** — exact string match versus normalised comparison
   for parcel identifiers, extents, and names. Lean **normalise before comparing**
   (trim, case, known abbreviations) and record the normalisation used, so a
   `mismatch` is a real disagreement, not a formatting artefact.
5. **Recompute trigger** — recompute findings on every fact change, on demand, or
   both. Lean **recompute on the `particular.corrected` event and on explicit
   re-run**, so the record and its checks never silently diverge.
