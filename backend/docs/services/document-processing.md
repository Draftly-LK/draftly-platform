# document-processing — implementation design

Companion to `backend/backend-implementation-plan-v0.md` and
`document-service.md`. This is the component behind `DocumentProcessingPort` —
the worker-side pipeline that reads an uploaded document and produces
non-authoritative candidate fields for lawyer verification.

Maps to plan **Phase 3** (the processing half), the `document_processing.py`
port (§4 ports), and the trust-boundary row *Derivatives* (§5.2).

## 1. What it owns

Reading an immutable document version and producing derivatives — page rasters,
OCR text with provenance, a document class, and candidate structured fields. It
runs in the `document_jobs` worker, never in an API request.

It does **not** accept uploads (`document_service` does), does **not** decide
correctness, and does **not** promote anything to a verified fact
(`verification_service` does, lawyer-gated). Everything it emits is a candidate,
marked non-authoritative and rebuildable.

## 2. Boundary with document_service

```text
document_service (sync)          document-processing (async worker)
  store original + enqueue  ──▶   claim job
                                  DocumentProcessingPort.process(version_ref)
                                    ├─ ClassifierPort
                                    ├─ OcrPort   (the escalation ladder)
                                    └─ ExtractorPort
                                  store derivatives + candidates
                                  mark version processed / manual_review
```

The original file is read, never written. All output is a derivative keyed to a
`ProcessingRun` and can be deleted and rebuilt without touching the evidence of
record.

## 3. Ports — the adapter pattern

Processing is not one call. It is a pipeline of stages, each its own port with
interchangeable adapters, so the processor, model, or provider changes by
swapping an adapter and an endpoint — no change to the worker or to
`document_service`.

```text
DocumentProcessingPort (orchestrates the stages)
  ├─ ClassifierPort   which document type is this?      → GeminiFlashLiteAdapter
  ├─ OcrPort          text + where it sits on the page  → DocumentAiAdapter (primary)
  │                                                       GeminiVisionAdapter (fallback)
  └─ ExtractorPort    structured fields from the text   → GeminiAdapter
```

Each adapter is selected by configuration. Adding Surya, Tesseract, or a
self-hosted model later is a new adapter and a settings value, nothing more.

## 4. Rasterization — render every page once, reuse three ways

Document AI accepts a PDF directly, so rasterization is not for Document AI. It
is needed for three other things, so it runs once up front and the result is
stored as a derivative:

1. **Cropping a region** — to cut a page by a bounding box you need a bitmap.
2. **The whole-page fallback** — the Gemini vision path needs a page image.
3. **The verification UI** — the lawyer is shown the page anyway.

Render each page with PyMuPDF or `pdftoppm` at about 300 DPI, locally and
deterministically. Record the render DPI or scale with the raster; the OCR
coordinate mapping in §6 depends on it.

## 5. The OCR escalation ladder

Document AI is the backbone — literal text, bounding boxes, and a confidence per
field. The Gemini vision tier is a confidence-gated fallback, scoped as tightly
as the available box allows. Three rungs:

```text
Level 0  Document AI on the whole PDF        → tokens + boxes + confidence
         │
         ├─ field confident         → keep. precise box provenance. normal review.
         │
Level 1  field LOW-confidence, box exists     → crop page to the box → Gemini reads the crop
         │                                       (precise provenance survives — the box is Document AI's)
         │
Level 2  Document AI gave little / no boxes    → render the WHOLE page image → Gemini reads the page
         │  (photo, dense scan, odd layout)       ask for fields + approximate regions
         │                                        (provenance degrades to "here is the page")
         │
Level 3  both weak / handwriting / degraded    → no machine value → manual entry, page shown to lawyer
```

### The key move: escalate the region, not the document

Do not hand a whole page to Gemini and ask it to read everything. Document AI
already located the field (the box). When its confidence on that box is low,
crop the page to that box and ask Gemini to read only the crop. Two things fall
out of it:

- **Provenance survives.** The source span (page and region) came from Document
  AI's box and stays true even though the text came from Gemini. Invariant 1
  holds — the lawyer clicks the field and still sees the exact spot on the scan.
- **The hallucination surface shrinks.** A model reading one cropped cell has
  far less room to invent than one free-reading a full page.

The whole-page path (Level 2) exists only when there is no box to crop. It is a
lower rung, and the cost is provenance, not correctness — the lawyer still
verifies against the page image.

### Guardrail: the fallback is escalation-gated, never the default

Whole-page Gemini fires only when Document AI is weak on that specific page. If
every page went to Gemini, the backbone, the cost control, and the
hallucination containment would all be lost. The classifier can pre-route here:
a page tagged photo or handwriting can skip straight to Level 2 or Level 3
instead of spending a Document AI call.

Level 3 is a legitimate, expected path, not a failure. The SRS lists handwriting
and severely degraded scans as explicit V0 limitations. The job there is to
route to manual entry cleanly, not to guess.

## 6. Coordinate mapping

Document AI returns **normalized coordinates (0–1)**, not pixels. To crop, or to
draw a highlight in the UI, multiply by the rendered page's pixel dimensions.
Record the render DPI or scale with each raster (see §4) so the mapping is exact
across the OCR space, the stored image, and the browser. Getting this wrong puts
crops and highlights in the wrong place.

## 7. Reconciliation — two readings are a trust signal

When both engines read the same box, the comparison itself is information:

| Document AI | Gemini (on the crop) | Result |
| --- | --- | --- |
| high confidence | not called | candidate, normal review |
| low, text `4471` | text `4471` | agreement — stronger candidate, still lawyer-gated |
| low, text `4471` | text `4474` | conflict — surface both, priority review |
| missing or unreadable | text `4474` | recovered — candidate, lowest trust, priority review |

Agreement between two engines that fail differently is a real signal. This is a
small ensemble, and it is stronger than either engine alone — which matches the
team's test finding that the dedicated OCR dropped data the Gemini tier
recovered. A disagreement flows straight into the verification layer's conflict
comparison step (plan Phase 4), which is already planned.

## 8. The honesty rules

Recovered and low-confidence values are the most useful (data otherwise lost)
and the most dangerous (hardest to read, so highest invention risk). Therefore:

- **Never auto-accept a recovered or machine value.** Always a candidate, always
  lawyer-gated. V0 already routes everything through verification.
- **Store both readings**, not only the winner. The lawyer sees "Document AI
  4471 (low) / Gemini 4474" beside the cropped image and decides.
- **Record which engine produced each field** (`source: document_ai` versus
  `source: gemini_recovered`) so the audit trail shows provenance per value.
- **No provider response ever sets a particular to verified** (Phase 3 exit
  gate).

## 9. V0 defaults

- **Classification:** a small Gemini tier (Flash-Lite class) routes each page to
  the right extraction path cheaply.
- **OCR:** Document AI primary; Gemini vision as the confidence-gated fallback
  on the ladder above.
- **Extraction:** the Gemini tier turns OCR text into candidate structured
  fields.

Model versions are named by tier here and pinned to exact IDs at implementation,
because the adapter makes the specific version a configuration value and a
hardcoded version number goes stale. The `OcrPort` keeps both adapters wired so
the choice can be made per document type on evidence, not up front.

## 10. Confidence threshold

The Level 0 to Level 1 threshold is tunable and must be measured, not guessed.
Set it conservative at first (escalate generously), then tune against a labelled
sample. Too high wastes Gemini calls; too low loses the recovery the fallback
exists for.

## 11. Effect on the SRS and architecture

The SRS and architecture documents name Google Document AI as the V0 processing
dependency. This design keeps Document AI as the primary OCR engine and adds a
scoped, confidence-gated Gemini fallback plus a Gemini classification and
extraction stage. It is an addendum to the named dependency, not a replacement,
so the documents need a short update rather than a rewrite. Track that as a
follow-up.

## 12. Test list

- **Unit:** ladder routing (which rung fires for which confidence and box
  state), coordinate mapping normalized to pixels, reconciliation outcomes,
  never-auto-accept enforcement.
- **Contract:** each port's adapter contract, provider-result normalisation into
  the common candidate schema, the `ProcessingRun` provider-metadata fields.
- **Integration:** PDF to rasters, Document AI adapter on a sample document,
  crop-and-escalate on a low-confidence field, whole-page fallback, manual-entry
  routing on an unreadable page.
- **Evaluation:** on a labelled sample, measure recovery yield (fields the
  fallback saved), false-recovery rate (fallback introduced a wrong value), and
  the agreement and conflict rates, to set the threshold and the review
  expectations.

## 13. Open decisions

1. **Confidence threshold value** — start conservative, tune on a labelled
   sample (§10).
2. **Classifier pre-routing** — how aggressively the classifier sends pages
   straight to Level 2 or 3 versus always trying Document AI first.
3. **Gemini approximate boxes at Level 2** — whether to ask for and store
   approximate regions or degrade to page-level provenance only.
4. **Exact model IDs** per stage, pinned at implementation.
