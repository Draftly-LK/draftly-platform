# Matter conversation mechanical review — synthetic only

Date: 2026-10-09. Task 6. Human visual and terminology approval remain pending.

## Scope and seams

The browser harness bundles the actual `MatterDashboard`, `MatterAssistantScreen`
and shared conversation components with production CSS and fonts. Its isolated
test bundle substitutes the token hook, Next navigation wrappers and synthetic
HTTP responses. It does not change production authentication or enable providers.
Separate migrated PostgreSQL integration tests cover owning commands, metering,
proposal concurrency and durable replay. Browser fixtures do not establish those
backend guarantees by themselves.

## Mechanical evidence

- Nine probes: Overview and full Assistant in English and Sinhala at 1440 and
  1024 CSS pixels; Sinhala Overview at 720 CSS pixels as a 200% reflow equivalent.
- No page overflow, serious/critical axe findings or unexpected browser errors.
- The narrow evidence panel contains keyboard focus and closes with Escape.
  Component tests also cover reverse Tab and focus restoration.
- One confirmation remains applied after navigation to the full view; one send
  remains saved after reload. No duplicate send, confirmation or retry occurs.
- A failed turn with recorded work retains its transcript and proposal/result
  visibility from both views, without offering an automatic duplicate retry.
- Case passages retain their saved corpus version and unverified status. Original
  source authorization is tested separately for owned, foreign and unavailable
  sources; the preview component is substituted only in those component tests.

Final screenshots, accessibility trees, probes and request counts are in
`iteration-3/`. `browser.json` records the synthetic seams and exact observations.
The later citation caption change to “Matched source passage” and conservative
unverified status for all matter legal passages are covered by 28 component tests
and the final CI suite. Those small changes postdate the three browser runs; the
captures are not represented as screenshots of that final caption.

## Iteration accounting

Three harness runs, no visual redesign loops. Run 1 stopped on an overly broad
harness assumption that the entire existing matter shell had one h1; it recorded
no axe violation or overflow. The embedded conversation uses h2 and preserves the
existing shell/page heading structure. Run 2 completed all nine layout probes and
stopped on a selector matching both the inline citation and citation chip. Run 3
used the exact inline citation control and passed the functional checks. Failure
logs remain in the private Task 6 workspace; prior synthetic captures are retained.

## Owner gates

- Human visual review of both views, actual browser zoom and dense matter content.
- Human Sinhala terminology and interaction wording review.
- Lawyer review of prescribed text and legal workflows; no prescribed text,
  approval/waiver wording or form templates were changed here.
- Production provider/data-processing approval remains governed by existing
  flags; tests used synthetic injections and no live provider transport.
- Task 7 owns scoped draft writes. Task 8 owns whole-branch integration, document
  provider/cancellation lifecycle and measured large-evidence latency/reentry.
