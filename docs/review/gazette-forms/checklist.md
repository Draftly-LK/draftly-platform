# Gazette forms (Form 08, Form 12) — review

Screens: `/matters/matter-rta-001/drafts/demo-form-08`, `…/demo-form-12`
(synthetic demo data), and the dev-only compare view `/dev/gazette/08`,
`/dev/gazette/12`.

## Evidence

- `compare-form-08-1..3.png`, `compare-form-12-1..2.png` — each gazette page
  (left, Gazette 1886/58 at 794 px) beside the Tiptap rendering (right),
  blanks drawn plain. Office box, item grid, tables, signature blocks, and
  attestation line up, and the running paragraphs break at the same words as
  the printed page.
- `workspace-field-by-field-1440.png`, `workspace-fill-in-document-1440.png`,
  `workspace-1024.png` — the two drafting modes.

## Checks run

- Mechanical: console clean and no page overflow at 1440, 1024, 767, and 390,
  in English and Sinhala; no raw message keys. Axe: no serious or critical
  violations on either route.
- Tokens: the design audit's per-route checks pass on both routes (radius,
  no shadows, icon sizes, row heights, fonts, tokens). Status is always icon
  plus text.
- Behaviour (`tests/e2e/gazette-forms.spec.ts`): the prescribed wording
  survives typing, delete, paste, and select-all delete; both modes share
  values; typed blanks persist; critical fields cannot be typed; clearing
  needs a reason; Form 12's lawyer-authored field corrects from the side list.
- Accuracy (`src/lib/gazette-forms/gazette-forms.test.ts`): the template text
  and the gazette transcription match in both directions.

## Human gates (escalated, not self-approved)

- Legal wording: the transcription is verbatim, including the printed
  spelling variants listed in `docs/reference/forms/README.md`. A lawyer must
  approve before either template leaves `DRAFT_TRANSCRIPTION`.
- Which gazette governs: the backend cites the 2022 amendment; these
  renderings are from the 2014 gazette.
- Backend fields with no printed blank (`sheet_no`, notary name and code,
  Form 12 discharge fields) and the Form 12 bindings listed in the README.
- Free-text blanks are stored on the device only; the draft API has no
  endpoint for them yet.

## Known pre-existing audit failures (not from this change)

The full e2e audits also fail on routes this change does not touch:
`/assistant` (axe `meta-refresh`, no navigation rail) and Clerk-provider
console errors on `/settings` and the document review route.
