# Documents layout review

- PASS: processing banner and document tables precede missing requirements.
- PASS: requirements start collapsed; Enter expands and Space collapses.
- PASS: English and Sinhala at 1440 and 1024 pixels have no page overflow.
- PASS: no serious or critical axe violations and no browser exceptions.
- PASS: frontend typecheck, lint and production build.
- PASS: backend lock, Ruff lint and formatting checks.
- PASS: backend focused suite: 187 passed, 23 database tests skipped.

Evidence: `results.json` and the collapsed/expanded screenshots. The preview
renders the real DocumentsScreen and RequirementsPanel with synthetic API data;
the app shell is omitted and browser font fallbacks are used. It does not
establish the full authenticated screen or font review gates.

Reproduce from `frontend/`: generate the stylesheet with
`pnpm exec tailwindcss -i src/styles/globals.css -o ../docs/review/documents/2026-10-14/preview.css`,
then run `node ../docs/review/documents/2026-10-14/browser-review.cjs`.
