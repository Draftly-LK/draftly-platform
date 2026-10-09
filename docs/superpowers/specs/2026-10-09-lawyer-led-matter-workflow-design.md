# Lawyer-led matter workflow design

## Approval and scope

The user approved explicit transactions and subjects within a matter on
2026-10-09 and instructed continuous execution through the success criteria.
The user subsequently chose V0 user/matter isolation and explicitly deferred
organization support. This design implements the six approved slices, with
Form 8 as the existing first instrument. Ten-form expansion and production
model/provider changes are separate decisions.

## Ownership and invariants

- Matter owns transaction scope, subject references, and transaction roles.
- Document owns immutable originals, page derivatives, grouping, extraction
  generations, and processing recovery.
- Verification owns fact versions, provenance, decisions, and eligibility.
- Task owns requirements, evidence sufficiency, manual work, and readiness.
- Check owns deterministic evaluations against exact reviewed fact versions.
- Matter agent owns persistent conversation and confirmation proposals.
- Draft, approval, and export retain their existing ownership and legal gates.
- Cross-module calls use public contracts and composition-root adapters.
- Customer records are user-scoped; every referenced resource is also checked
  against its matter. A supplied subject, document, or evidence ID is never
  sufficient proof of access.
- No source, extracted original, lawyer decision, or prior approved snapshot is
  overwritten. Only current eligible reviewed facts feed approved outputs.
- Legal text, prescribed template copy, and approval/waiver language remain
  human-owned. No approval or provider-data flag is enabled by this work.

## Subjects and transactions

Use stable matter-local subject IDs for parties and parcels, distinct from
protected identity values. Transactions reference parcel subjects and party
roles; documents may support more than one transaction. A role inferred by a
model remains a proposal until the lawyer records it.

A fact's scope is its transaction, subject, and governed fact type. Versions
and conflict selection use that scope. Unassigned candidates stay visible but
cannot be silently attached to the first party or parcel. Legacy unscoped facts
remain readable and require an explicit association when ambiguous.

The confirmed-fact contract preserves scoped values. Compatibility projections
may expose a fact type only when it has one unambiguous eligible value. Drafting
uses an explicit transaction and subject/role bindings; it never chooses a
latest matter-wide value to resolve ambiguity.

## Processing and corrections

Every uploaded file retains its source state and latest persistent run, with
failure reason, page outcomes, and an actionable retry or manual-review path.
Success is read from run state, never source-ID presence. Unknown state is not
success. Remove artificial processing delays.

Changing document classification or grouping creates a new interpretation
generation over unchanged originals. The old generation and decisions remain
available. Affected candidates become stale immediately and cannot be approved.
Dependent reviewed facts, requirement links, check results, drafts, approvals,
and queued outputs cease to qualify until their owning services re-evaluate
them. Extraction refresh uses the corrected type and fragments, retains OCR
where valid, and records failure without restoring old authority.

Page review permits corrected ranges, including multiple source files. Invalid,
out-of-range, or ambiguous overlap is refused with a recoverable response.

## Canonical register and lawyer input

Facts is the matter register before a form exists. It shows candidate and
reviewed values, original extraction, supporting document/page/text, confidence,
scope, review status, conflicts, reviewer/time, and decision history.

Accept, correct, reject, and associate decisions are backend commands with
authorization, concurrency checks, replay protection, and audit references.
Corrections create successors; rejection remains distinguishable from a missing
value. Manual information records origin, actor, time, reason, and evidence.
Evidence-free input can be saved as unverified information; it does not satisfy
evidence requirements or feed an approved form. A reviewed fact requires the
existing evidence policy and a current readable source.

Supporting excerpts are validated against stored page OCR. Exact matching can
be labelled a text span; otherwise show page-level attribution and full page
text honestly. A model-supplied excerpt is not accepted as grounding by itself.
Original page/source access remains available beside every decision.

## Requirements, checks, and progress

Documents contains uploaded evidence and missing requirements, with linked
documents and separate receipt and sufficiency states. Existing missing-document
URLs resolve to this connected view. Linking validates all references and is
idempotent. Receiving or processing a document never accepts its sufficiency.

Checks distinguishes deterministic results, governed manual tasks, and evidence
review. A manual completion records actor/time and reason where required. It
cannot directly set computed satisfaction, waive mandatory policy, or rewrite a
failed automated result. Corrections reopen only affected dependent work while
preserving earlier decisions.

Readiness comes from backend state and identifies pending processing,
classification/grouping, subject assignment, candidate review, missing evidence,
manual work, stale checks, and unavailable services. Overview routes to the
earliest actionable unresolved dependency. An unavailable checklist is unknown,
not zero blockers. Drafting is an optional action, not compulsory completion.
Live routes do not consume the demo workflow store.

## Conversation and assistant actions

Overview embeds the same conversation component and session used by the full
Assistant view. The transcript survives refresh. Source links open matter
evidence or permitted legal citations. Missing providers/evidence produce
explicit unavailable or abstention states.

Review and requirement actions are persistent proposals with proposed,
confirmed, declined, stale, executed, or failed states. Confirmation rechecks
capabilities, practising status where required, matter access, target versions,
and evidence eligibility before calling the owning service. Replayed confirmation
returns the prior result rather than another mutation. The assistant does not
approve forms, waive legal policy, or promote its own suggestions.

Existing retry/SSE work in `.local-tools/landing-assistant-fixes` must be inspected
and selectively integrated with its tests and migration; unrelated landing-page
changes stay outside this branch.

## Optional Form 8

The lawyer selects an existing supported template, transaction, parcel, and
party roles. Reviewed facts bind by scope to exact fact versions. Missing fields
explain whether information is absent, unreviewed, conflicting, stale, or
unassigned. Form-field review remains in drafting and links to canonical facts.
Correction refresh creates an unapproved successor draft; historical approvals
and outputs remain pinned. Existing legal/readiness gates still control approval
and export; populated fields do not imply registration readiness.

## Evaluation and verification

Create independent synthetic documents with conspicuously synthetic names and
identifiers, including mixed/rotated/scanned pages, two parties/parcels,
conflicts, uncertain/unsupported fields, missing information, and partial failure.
Do not derive fixture values from the real local case or reuse real-shaped
identifiers from it. Review the synthetic reference and numerical target with
the owner before claiming extraction improvement.

Report supported classes/fields, supported facts extracted and missed,
unsupported fields, uncertain values, evidence precision, and abstentions.
Deterministic provider doubles prove contracts and persistence, not OCR accuracy.
A stronger model is evaluated only if capability remains a measured bottleneck.

The persistent API walkthrough covers upload, processing, grouping, scoped fact
review, conversation, requirement/manual decisions, and an optional Form 8.
It also covers cross-user/matter denial, correction invalidation, refresh,
concurrency, and retry without duplicate mutations. Use disposable PostgreSQL
and local storage; never a production database. Real-case OCR remains outstanding
unless documented existing approvals permit it.

## Delivery

Each slice ships with regression/integration tests, contract/migration updates,
directly related documentation, and an atomic Conventional Commit using E5,
E7, or E8-7 as appropriate. Inspect explicit staged paths for credentials/client
data. Review major slices independently and fix important findings before
proceeding. Run the repository frontend, backend, Markdown, and migration gates.
Record commands/results, coverage limits, walkthrough evidence, commit-to-goal
mapping, and unresolved owner decisions. A human merges the PR.
