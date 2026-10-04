# Gazette form sources

Source material for the Tiptap gazette templates in
`frontend/src/lib/gazette-forms/`. The application serves the **English**
forms. The Sinhala forms are kept separately and are not served.

## Files

- `../1886-58_E.pdf` — Sri Lanka Gazette Extraordinary No. 1886/58 of
  2014.10.31 (Part I, Section I), the Registration of Title Act forms, in
  English. Copied from the research corpus
  (`gazettes/registration-of-title/gazette-1886-58-2014-10-31-en.pdf`).
- `../1886-58_S.pdf` — the same gazette in Sinhala. Recovered from commit
  `64d0725` on `feat/tiptap`.
- `pages/en/page-NN.png`, `pages/si/page-NN.png` — 150 dpi renders of the
  pages the templates use. English: pages 04–06 (Form 08) and 14–15
  (Form 12). Sinhala: pages 04–06 (Form 08) and 13–14 (Form 12). The page
  numbers differ because the two language editions paginate differently.
- `transcriptions/en/form-NN.txt`, `transcriptions/si/form-NN.txt` — each
  form's printed text, line by line, as printed. Dotted leaders are kept as
  dots.
- `../tools/fm_abhaya_to_unicode.py` — produces the Sinhala transcriptions.

## How the transcriptions were made

**English.** The English PDF has a real text layer. Each transcription was
taken from it in reading order (the office-use box and the land-parcel block
are two-column layouts, so the raw layer interleaves them), then checked in
both directions against the layer: every transcribed line is in the PDF text
and every line of the form's PDF text is in the transcription. The rendered
pages were read against the result.

**Sinhala.** The PDF's text layer is in the legacy FM Abhaya font encoding:
ASCII code points drawn as Sinhala glyphs. The converter maps FM Abhaya to
Unicode Sinhala and moves the pre-base vowel signs (ෙ, ෛ) after their
consonant. It does not correct anything.

```sh
uv run --with pymupdf python docs/reference/tools/fm_abhaya_to_unicode.py \
  docs/reference/1886-58_S.pdf 08 > docs/reference/forms/transcriptions/si/form-08.txt
```

Each Sinhala transcription was proof-read against the page image. Glyph
mappings were confirmed on unambiguous words. For example, `ð` is ජි because
it spells "රෙජිස්ට්‍රාර්", and `Y` and `I` are distinct code points (ශ and ෂ).

## Accuracy guarantees

`frontend/src/lib/gazette-forms/gazette-forms.test.ts` compares every template
with its transcription in both directions, ignoring only whitespace and dotted
leaders:

- every printed fragment in the template occurs in the gazette text;
- every line of the gazette text occurs in the template.

A change to a single character of prescribed wording fails the test.

## Printed spellings kept as printed

These are the gazette's own spellings. They are legal copy, so they are not
corrected; they are recorded here for the legal team.

### English

| Form | Where | As printed | Note |
| --- | --- | --- | --- |
| 08 | Transfer clause | "It is hereby request to register" | Reads as "requested" |
| 08 | Life-interest clause | "was revocated" | Reads as "revoked" |
| 08 | Attestation | "stipulated in under Section 44" | Doubled preposition |
| 08, 12 | Attestation | "Official Frank" | As printed |
| 08 | Item 1 | "(l) No. of the parcel, if condominium property" | Form 12 prints "No. of the unit" |
| 08 | Item 6 | "Registration Fee : ....", no "Rs." | Form 12 prints "Rs." |

### Sinhala

| Form | Where | As printed | Note |
| --- | --- | --- | --- |
| 08 | Item 5 caption | ප්‍රතිශ්ඨාව | The transfer clause prints ප්‍රතිෂ්ඨාව |
| 08 | Transfer clause | ලේඛණයේ | The office box prints ලේඛනයේ |
| 08 | Life-interest clause | … වන ම විසින් … | Reads as "වන මා/මම" |
| 08 | Life-interest signature | ජිවිත | The clause above prints ජීවිත |
| 12 | Release clause | ලේඛණයේ | As Form 08 |
| 12 | Witness statement | ගැණුම්කරු | Item 4 prints ගැනුම්කරු |
| 12 | Release clause | (උකස් දීමනාකරු) වන මම | Names the mortgagor as the releasing party |

## Open questions for the legal team

- **The two language editions differ.** The Form 12 release clause in
  English has the mortgagee ("I … of … (mortgagee) hereby discharge the land
  belonging to … (mortgagor)"). The Sinhala edition names the mortgagor
  ("උකස් දීමනාකරු") as the releasing party. Form 08 item 6 prints "Rs." in
  Sinhala but not in English. Which edition prevails, and whether the
  difference is intended, is for the legal team.

- **Which gazette governs.** The backend registry cites the 2022 amendment
  for Forms 8 and 12. These renderings come from the 2014 gazette 1886/58.
  Whether the 2014 layout and wording are still the prescribed ones needs
  confirming before any template leaves `DRAFT_TRANSCRIPTION`.
- **Fields with no printed blank.** The backend maps `sheet_no`,
  `notary_name`, and `notary_code` on both forms, and the Form 12 discharge
  fields. The printed 2014 forms have no blank for any of them. The workspace
  lists them under "Not printed on the form"; nothing is placed on the page
  for them.
- **Mapping choices to confirm.** Form 12 item 3 (උකස් දීමනාකරු, the
  mortgagor) is bound to `registered_owner_name`. The item 5 table's
  "දිනපොත් අංකය" and "දිනය" columns are bound to `mortgage_reference` and
  `mortgage_registration_date`.
