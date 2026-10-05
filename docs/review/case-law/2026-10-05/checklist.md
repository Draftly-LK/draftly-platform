# Case-library reconciliation with current main

## Scope

PR #53 was updated from main `a66a3dc` on 2026-10-05. The only content conflict
was `frontend/src/components/library/library-screen.tsx`. Main's statutory
loading skeleton, offline/empty/error states, retry action, input boundaries and
unshadowed summary were retained inside the statute tab. The case tab, catalogue,
reader and standalone search retain their original API contracts and behavior.

Case components now follow current CLAUDE.md: shared secondary/primary button
classes, pill controls and signal chips, 16 px card radii, 12 px multiline input
radii and `border-control` input boundaries. Main's shared shell, sidebar,
dashboard, auth, tokens and deployment changes were incorporated unchanged.
The older 2026-10-04 captures remain historical evidence; these captures supersede
their 6 px case-component styling. Publication/provider approval gates remain.

## Verification

- PASS: frontend 595 tests in 62 files, lint, typecheck and production build.
- PASS: backend lock, Ruff check/format, mypy (352 files), CI suite
  (1,122 passed, 3 expected failures).
- PASS: Markdown lint and conflict-marker/diff whitespace checks.
- PASS: populated search in English at 1440 and 390 px, Sinhala at 1024 and
  390 px; no horizontal overflow, page exceptions or serious/critical axe issues.
- PASS: computed shared primary gradient, navy text, pill control radii and
  input border `rgb(123, 136, 153)`.
- PASS: approved synthetic reader renders escaped script markup and paragraphs.
- PASS: visual inspection of English desktop and Sinhala mobile captures.

The browser harness bundles actual case/library components with the production
build's CSS and fonts. Synthetic token and API fixtures supply records; the app
shell is represented by a test-only main wrapper. This is a component check,
not a live Clerk session or new shared-shell approval. No production mock or auth
override was added. Harness-only response/font/context/title issues were corrected
before recording the passing run.

The production build emitted the existing webpack 270 kiB cache-serialization
performance warning. Backend retains its existing Starlette test-client warning.
The previously documented nine full-suite matter-agent fixture failures remain
outside this frontend reconciliation; their paths are unchanged.
Human Sinhala terminology, visual identity and full-text publication approvals
remain separate release decisions.

## Captures

- [English desktop](en-1440-search.png)
- [English mobile](en-390-search.png)
- [Sinhala desktop](si-1024-search.png)
- [Sinhala mobile](si-390-search.png)
- [Approved synthetic reader](reader-1024.png)
