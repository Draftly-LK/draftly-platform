# Draftly landing-page audit

The existing SAMMY-style components, sections, artwork and layout were retained.
The page is a saved deployment mirror, rather than the original Next.js source.

## Fixed and verified

- The section label is `WHAT DRAFTLY DOES` at all three requested sizes.
- No existing pilot-intake endpoint or configured form service was found. The
  existing Node preview server now supports `POST /api/pilot-requests` and saves
  validated requests privately outside the served mirror.
- The existing inline form has validation, submitting, success, server-error and
  network-error states. It disables submission while running and guards repeated
  submit events. Accepted emails are stored once, including retries.
- Desktop `TRY DRAFTLY BETA` and mobile `TRY BETA` redirect through `/app` to the
  application frontend, locally verified at port 4310. Mobile prefetching is
  disabled to avoid cross-origin Next.js payload requests.
- `EXPLORE THE RESEARCH`, header Research and both footer research links open
  the existing `/lab` research page.
- Footer Overview now targets the existing product section; About targets the
  existing pilot section. Navigation, mobile-menu Escape/focus restoration,
  keyboard outlines and footer layout were checked.
- Restored missing original ASCII artwork and the shared legal-page chunk at
  its expected paths. Fixed favicon query mapping, legal-page favicon metadata,
  stale homepage metadata, mirror hydration errors and the copyright encoding.

## Validation and evidence

Landing-page and application frontend lint and TypeScript checks pass.
The dedicated six-test landing-page Playwright suite uses the repository's
existing Chromium setup. It covers three viewport audits, destinations, form
states/duplicate prevention and API validation/idempotent retries.
All six cases passed in the final full run, including the legal-page
console/network checks.
The two changed Markdown documents also pass scoped Markdown lint.

```powershell
# From landing-page
pnpm.cmd lint
pnpm.cmd typecheck

# From frontend
pnpm.cmd lint
pnpm.cmd exec tsc --noEmit
node node_modules/@playwright/test/cli.js test --config playwright.landing.config.ts
```

The viewport audits found no horizontal overflow, checked text/control clipping,
console errors or failed HTTP responses. Expected errors are deliberately mocked
in the form-state test. A harmless unused-preload warning remains in browser
inspection. The broader application end-to-end suite was not run.

Safe local submissions used `draftly-pilot-test@example.test` and
`draftly-browser-test@example.test`. The API returned HTTP 200 with
`{"accepted":true}`; the tests verified the stored email and single record on
retry. No email was sent.

| Viewport | Page screenshot | Footer screenshot | Audit |
| --- | --- | --- | --- |
| 375 x 812 | [Page](final-375x812.png) | [Footer](footer-375x812.png) | [JSON](audit-375x812.json) |
| 768 x 1024 | [Page](final-768x1024.png) | [Footer](footer-768x1024.png) | [JSON](audit-768x1024.json) |
| 1440 x 900 | [Page](final-1440x900.png) | [Footer](footer-1440x900.png) | [JSON](audit-1440x900.json) |

## Changed files

- `landing-page/pilot-api.mjs`, `pilot-form.ts`, `serve.mjs`: local intake,
  accessible form states, application redirect and asset serving.
- `landing-page/patch-site.mjs`: reproducible in-place deployment patches.
- Existing mirror chunks 84, 116, 347, homepage/layout chunks, focus stylesheet,
  homepage/research HTML and legal-page favicon metadata.
- Restored `ascii-{magnifying-glass,phone,letter,policies,radar}.html`,
  `lady-justice-v6.html`, and shared chunks under dpa/security/service-description.
- `landing-page/package.json`, `.gitignore`, `tsconfig.json`,
  `eslint.config.mjs`, `README.md`: checks and local-server documentation.
- `frontend/playwright.landing.config.ts`,
  `frontend/tests/landing-page/landing.spec.ts`: browser regression coverage.
- This report, audit JSON and six screenshots.

The existing logo and user-authored `content.md` changes predate this audit.
Unrelated repository changes were retained.

## Remaining hosting requirements

- Set `DRAFTLY_APP_URL` to the actual deployed application URL; none was supplied.
- Run the Node server and configure a private persistent `PILOT_REQUESTS_DIR`.
  Static-only hosting cannot run this API. Local capture does not deliver email
  or notify a team; that requires an approved real service/integration.
- The mirrored legal/security documents still describe SAMMY Labs. The
  responsible-legal-AI CTA opens the existing security document. These links
  function, but their content needs owner review before publishing as Draftly.
  Legal wording was preserved rather than authored during this audit.
