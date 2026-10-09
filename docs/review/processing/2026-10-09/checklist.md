# Processing recovery review

Date: 2026-10-09. Scope: Task 1 persisted processing and recovery.

## Evidence and scope

The browser harness renders the actual `ProcessingScreen`, `AppShell`, API
client, English messages, CSS, and fonts. It replaces the token hook, Clerk
hooks, Next navigation, and HTTP responses with synthetic doubles. It is a
component browser review, not an authenticated backend journey. Every file,
matter, run, and response in these images is synthetic.

- [Failed run at 1440 px](failed-1440.png)
- [Failed run at 1024 px](failed-1024.png)
- [Retained page warnings at 1024 px](partial-1024.png)

These are review captures, not human-approved visual baselines. The harness
and raw probes remain in the ignored implementation workspace.

## Checked

- PASS: no page horizontal overflow at 1440 and 1024 px.
- PASS: zero serious or critical axe findings in the failed-run views.
- PASS: zero browser console, page, or failed-request errors in the harness.
- PASS: status uses icon and text; failure reason, retry, refresh, and manual
  review are visible. A failed attempt does not offer successful continuation.
- PASS: keyboard Tab reaches refresh and retry; focused button has a visible
  2 px outline in `rgb(27, 51, 88)`.
- PASS: retry reads the source again and sends `If-Match: "3"`; the failure
  remains after the retry response and page reload.
- PASS: retained OCR failure and uncertain rotation show page-specific warnings
  with a manual-review label and document-inbox link.
- PASS: body font resolves to IBM Plex Sans with Noto Sans Sinhala fallback.
  Existing canvas resolves to `rgb(243, 245, 248)`; see the inherited mismatch
  in [issues](issues.md).
- PASS: focused automated tests cover unknown results, provider unavailability,
  success, retained-page warnings, pagination, stale versions, busy actions,
  replacement, and distinct empty/error views.

## Pending human and integration checks

- Human visual identity and workflow approval remain pending.
- Authenticated processing against a running backend remains pending; the
  browser harness does not prove production authentication or database writes.
- Sinhala browser layout and the 200% text-expansion visual gate remain pending.
  English and Sinhala message structure is covered by automated tests.
- Browser axe coverage is limited to the two failed-run widths above; the
  partial-page capture received visual inspection, not a separate axe run.
