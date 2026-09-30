# Gazette form sources

Source material for the Tiptap gazette templates in
`frontend/src/lib/gazette-forms/`.

## Files

- `../1886-58_S.pdf` — Sri Lanka Gazette Extraordinary No. 1886/58 of
  2014.10.31 (Part I, Section I), the Registration of Title Act forms, in
  Sinhala. Recovered from commit `64d0725` on `feat/tiptap`.
- `pages/page-NN.png` — 150 dpi renders of the pages the templates use:
  pages 04–06 (Form 08) and 13–14 (Form 12).
- `transcriptions/form-NN.txt` — each form's printed text in Unicode, line by
  line, as printed. Dotted leaders are kept as dots.
- `../tools/fm_abhaya_to_unicode.py` — produces the transcriptions.

## How the transcriptions were made

The PDF's text layer is in the legacy FM Abhaya font encoding: ASCII code
points drawn as Sinhala glyphs. The converter maps FM Abhaya to Unicode
Sinhala and moves the pre-base vowel signs (ෙ, ෛ) after their consonant. It
does not correct anything.

```sh
uv run --with pymupdf python docs/reference/tools/fm_abhaya_to_unicode.py \
  docs/reference/1886-58_S.pdf 08 > docs/reference/forms/transcriptions/form-08.txt
```

Each transcription was proof-read against the page image. Glyph mappings
were confirmed on unambiguous words. For example, `ð` is ජි because it spells
"රෙජිස්ට්‍රාර්", and `Y` and `I` are distinct code points (ශ and ෂ).

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
