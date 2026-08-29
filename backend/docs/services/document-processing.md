# Draftly V1 Document Processing

Proposal. This lives in the research repo and does not describe what the platform
currently implements.

The pipeline:

```text
Upload
  -> Cloud Vision OCR
  -> quality / blank check
  -> deterministic rotation (with abstention)
  -> page classification
  -> split and group pages
  -> derivatives
  -> Gemini structured extraction
  -> store
  -> user review
```

## 1. Upload

Store the original file in GCS and never modify it. Record its GCS key,
generation, hash and matter ID in Neon. Every later artifact is a derivative that
can be rebuilt from the original, so the original stays the single source of
truth for any dispute about what the document said.

## 2. Cloud Vision OCR

Render each page and run Cloud Vision `document_text_detection` with language
hints `si`, `ta`, `en`. Keep the full response: text, words, per element
confidence, detected languages, and the four point bounding polygons.

Vision is the only engine measured on this corpus that reads Sinhala and Tamil.
On the same 26 pages, Vision produced 6,419 Sinhala and 2,083 Tamil characters
while docTR, RapidOCR and the Document AI OCR processor each produced none. Since
roughly 29% of the corpus by character is Sinhala or Tamil, that difference
decides the engine.

Keep the polygons in their original vertex order. Flattening them to
`[x0, y0, x1, y1]` rectangles destroys the rotation signal, and it cannot be
recovered afterwards.

## 3. Quality and blank check

Retain every page. Mark it `likely_blank`, `ocr_sparse` or `ocr_failed`, and
exclude it from automated extraction only when appropriate.

A page that looks empty to an ink-ratio check may still carry a stamp, a
signature, a marginal note or a handwritten endorsement, any of which can matter
legally. Dropping such a page loses evidence silently. Flagging it keeps it
visible to the reviewer while keeping it out of the extraction prompt.

The distinction also separates two failures that look identical downstream: a
genuinely blank separator page, and a page the pipeline could not read.

## 4. Rotation, with abstention

Detect orientation from the vertex order of high confidence word polygons. Vision
emits vertices starting at the text's own top left and running clockwise, so the
first edge points along the reading direction. Weight each word's vote by
confidence multiplied by top edge length, then snap to 0, 90, 180 or 270 degrees.

Accept the result only when both hold:

- at least 10 usable words on the page
- the dominant orientation holds at least 70% of the weighted vote

Below either threshold, mark the page `uncertain`, leave it unrotated, and flag it
for review. Guessing an orientation on a legal instrument is worse than leaving it
alone, and a page with almost no text cannot support a decision either way.

When rotating a page, transform every OCR polygon into the corrected page
coordinate system. Store the original and corrected orientation, the corrected
page dimensions and the transformed polygons alongside the originals. Without
this, browser overlays are drawn in the wrong places on exactly the pages that
were rotated, and the error is invisible in the OCR text itself.

This step is not cosmetic. Across the 26 page sample, 16 pages required rotation
in three different directions, including one fully inverted page. Reading order,
page grouping and any later region work are all wrong on an uncorrected page.

Record the detected orientation, the correction applied, the vote share, the
usable word count and the status on every page.

## 5. Page classification

Classify all pages of an upload in a single Gemini 2.5 Flash-Lite call, not one
call per page. Supply the document types expected from the matter checklist and
ask for one row per page.

For each page the model returns:

- `type_id`, a checklist type or `other`
- `suggested_name`, a short name, only when `type_id` is `other`
- `starts_new_document`, whether this page begins a new logical document
- `model_reported_confidence`

`starts_new_document` is what makes splitting possible. Type alone cannot separate
two consecutive documents of the same type, which is common in a bundle holding
several instruments of one kind. Without a boundary signal they merge into one
logical document and the second one's fields are attributed to the first.

A `suggested_name` is a hint for the reviewer. It never becomes a permanent
platform document type on its own, because that would let model output silently
expand the product's vocabulary. Adding a type stays a deliberate change.

Show low confidence classifications as low confidence in the interface rather than
resolving them quietly.

### Batching and truncation

Classification and extraction are separate steps, so the naive shape sends every
page to Gemini twice: once to find out what it is, once to pull fields out of it.
On the 26 page sample that is 30 calls and about 19,400 prompt tokens, with the
full OCR text paid for twice.

Batching all pages into one call removes that duplication. Sending only the first
300 characters of each page is a further proposed optimization, on the reasoning
that a page's type is usually carried by its heading, form number and opening
lines.

| approach | calls | prompt tokens |
| --- | --- | --- |
| one call per page, full text | 30 | ~19,400 |
| one batched call, 300 chars per page | 5 | ~11,600 |

The batching saving is arithmetic. The truncation saving is not measured: whether
300 characters preserves the same classification and boundary decisions has not
been tested, and a page whose distinguishing content sits below a long letterhead
could be misclassified. Implement truncation with a fallback that re-sends more of
the page text when `model_reported_confidence` is low or `starts_new_document` is
uncertain, and sweep the character budget once a second labelled matter exists.

## 6. Split and group pages

Form logical documents using both signals: start a new group where
`starts_new_document` is true, and treat a change in `type_id` as a boundary as
well. Run extraction once per logical document.

Do not classify a multi-page upload from its first page. One upload in the sample
is a 16 page bundle holding several instruments; a single classification taken
from page one applies one schema to all of it and mislabels most of the pages.

## 7. Derivatives

Produce and store in GCS:

- corrected page images in WebP
- OCR JSON, including polygons and per word confidence
- plain OCR text in reading order

The bounding box overlay can be drawn in the browser from the corrected image and
the OCR JSON, so it does not need to be a stored artifact. Storing it costs
roughly 400 KB per page with no information the client cannot already derive.
Cache it later if profiling shows a reason.

The original upload stays untouched.

## 8. Structured extraction

Send each logical document's OCR text to Gemini 2.5 Flash-Lite with the field
schema for its type. Return candidate fields with a value, a page number and a
model reported confidence.

Flash-Lite is the measured choice. Across four models on the same prompt and the
same documents, it produced the best F1 (0.635), ran in 2.6 seconds per document,
and cost about a quarter of Gemini 2.5 Flash. That comparison rests on four
labelled documents and 37 fields, so treat it as a starting position rather than a
settled result.

Every value stays a string end to end. A parcel number such as `0021` parsed as an
integer becomes `21`, which is a different parcel.

## 9. Grounding is out of scope for V1

V1 does not establish exact field-level provenance. Therefore, it cannot prove
which OCR words produced each extracted field. All fields remain unverified until
reviewed.

The interface has to carry that honestly:

- every extracted field is labelled an unverified candidate
- no field click highlighting, and nothing that implies a field has an exact
  source region
- the reviewer corrects and approves each field

Field to polygon grounding is the obvious V2 candidate, and it is what would let
the interface show a reviewer where a value came from.

## 10. Storage

Neon holds GCS object references, processing run metadata, page classifications
with confidence and boundary flags, logical document groupings, candidate
structured fields and review state.

Model output is never marked verified automatically. A field becomes verified when
a person approves it, and the record keeps who approved it and when.

## 11. Security and retention

These documents carry NICs, names, addresses and consideration amounts.

- private storage only, no public objects
- encryption in transit and at rest
- tenant scoped authorization on every read and write
- short lived signed URLs for client access
- least privilege service accounts, separated by function
- retention and deletion configurable per matter, with deletion covering
  derivatives as well as originals
- never write OCR text or extracted personal data into logs or traces

## What was removed

The Document AI escalation ladder and the multi provider adapter discussion are
both gone. Document AI's OCR processor returned no Sinhala or Tamil on any page
tested, so it cannot serve this corpus, and a fallback ladder that cannot read the
documents adds cost and complexity without adding coverage.

Keep the provider boundary as a plain interface so a second engine can be added
when there is evidence for one. Do not build the ladder before that evidence
exists.

## Evidence and limits

The measurements above come from `ocr-benchmark/` in this repo, over one matter:
7 uploaded files and 26 pages, of which 4 files carry gold labels totalling 37
fields. The uploads are an identity card, a survey plan, a title certificate, a
16 page Form 8 bundle, an RTA sale instrument, a vendor board resolution and a
payment cheque.

No splitting has been run on them, so 7 is a count of uploaded files rather than
of logical documents. The Form 8 bundle alone almost certainly holds several, so
the logical document count will be higher than 7 once step 6 runs.

That is enough to choose an OCR engine, since the Sinhala result is categorical
rather than marginal. It is not enough to settle extraction accuracy, where the
four models sit within a few labelled fields of each other.

Sinhala field extraction is still unmeasured. All 37 labels are Latin or numeric
identifiers, so a model that ignored every Sinhala word on the page would still
score well. Labelling fields whose values are Sinhala, such as names, addresses
and boundaries, is what would close that gap.
