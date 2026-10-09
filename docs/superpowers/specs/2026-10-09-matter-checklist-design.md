# Matter checklist design

The matter Overview is the lawyer's working checklist. Checks remains the
evidence and findings view. The header shows recorded completion, assessment
uncertainty, and the next actionable task.

## Agreed behavior

- Group work into documents and facts, evidence and checks, drafting, signing
  and attestation, stamping and registration, and final completion.
- Rows show status, reason, evidence, origin and a direct action. Details retain
  assignment, completion actor/time and history. Completed work is collapsed.
- Approved rules determine legal requirements. Novel agent suggestions require
  lawyer acceptance before joining the list. Lawyers may add operational tasks.
- Processing completion comes from the document service. Evidence acceptance,
  review, approval and registration remain decisions of their owning services.
- Dependency changes project affected completions as needing review without
  erasing the prior decision. Unrelated tasks retain their state.
- Progress counts current applicable leaf tasks. Unaccepted suggestions,
  cancelled/superseded tasks and non-applicable tasks are excluded. Unknown
  applicability shows assessment uncertainty. No known tasks never means 100%.
- Progress does not establish legal readiness or approval/export eligibility.

## Constraints

Use existing service boundaries, capabilities, concurrency and retry conventions.
Keep original evidence and decision history. Do not change statutory text,
templates, waiver/approval language, rates, deadlines or legal policy. All test
data and screenshots are synthetic. Use Draftly tokens and English/Sinhala.

## Baseline

Implementation starts from main commit `77f94c4`, including PRs #102, #103 and
PR #104. Preserve the 75% global branch coverage floor, bundled fonts and the recent
Overview/assistant simplification. Work only on `dev/codex/matter-checklist`;
a human merges the PR.
