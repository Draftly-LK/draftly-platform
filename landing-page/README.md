# SAMMY Labs local mirror

This directory uses
[`website-scraper`](https://github.com/website-scraper/node-website-scraper)
to download the public pages and required assets from `https://www.sammylabs.com/`.

## Commands

```powershell
pnpm.cmd run serve
```

The scrape is written to `site-mirror/`, preserving host and URL structure.
The preview server maps the downloaded SAMMY Labs, Fontshare, and Google Fonts
host directories into one local origin and understands the scraper's
query-string filenames. The scraper intentionally limits requests to those
asset hosts. The destination must not already exist; rename or remove an old
mirror before running the scrape again.

Use `pnpm.cmd run scrape:rendered` for the browser-rendered version. It waits for
the client-rendered homepage and also captures the Lady Justice and gavel
animation data files that the site requests dynamically from JavaScript.

This is a deployment mirror, not the original React/Next.js source code or its
backend services. Features that depend on the original server, private APIs,
forms, analytics, or live data may not work offline.

## Draftly landing-page audit fixes

The existing page and component structure are retained. `pilot-form.ts` is the
editable implementation of its existing inline email form. `pnpm.cmd run patch`
compiles that component into the saved deployment and reapplies the audit fixes;
it uses the existing toolchain installed in `../frontend/node_modules`.

The local server implements `POST /api/pilot-requests`. It validates the email,
rejects cross-origin browser requests, limits repeated attempts, and saves each
email once in `.local/pilot-requests/`. Success means the request was saved;
there is no email delivery or external form service. This directory is private,
excluded from Git, and never served as website content. Set `PILOT_REQUESTS_DIR`
to a private persistent directory when deploying; ephemeral hosting would lose
requests on restart.

`TRY DRAFTLY BETA` links to `/app`, which redirects to `DRAFTLY_APP_URL`. Its
local default is `http://127.0.0.1:4310/`, the application frontend's review port.
Set the deployed application URL before publishing. Research CTAs open `/lab`.

```powershell
$env:DRAFTLY_APP_URL = 'http://127.0.0.1:4310/'
pnpm.cmd run lint
pnpm.cmd run typecheck
```

The landing-page browser suite uses the repository's existing Playwright
installation. Run from `frontend/`:

```powershell
node node_modules/@playwright/test/cli.js test --config playwright.landing.config.ts
```

It checks 375 × 812, 768 × 1024, and 1440 × 900, navigation and CTA destinations,
keyboard access, form states, duplicate submission prevention, and durable local
intake. Final screenshots and audit results are written to
`docs/review/landing-page/2026-09-18/`. Test email addresses use `example.test`.
