# SAMMY Labs local mirror

This directory uses [`website-scraper`](https://github.com/website-scraper/node-website-scraper) to download the public pages and required assets from `https://www.sammylabs.com/`.

## Commands

```powershell
npm.cmd install
npm.cmd run scrape
npm.cmd run serve
```

The scrape is written to `site-mirror/`, preserving host and URL structure. The preview server maps the downloaded SAMMY Labs, Fontshare, and Google Fonts host directories into one local origin and understands the scraper's query-string filenames. The scraper intentionally limits requests to those asset hosts. The destination must not already exist; rename or remove an old mirror before running the scrape again.

Use `npm.cmd run scrape:rendered` for the browser-rendered version. It waits for the client-rendered homepage and also captures the Lady Justice and gavel animation data files that the site requests dynamically from JavaScript.

This is a deployment mirror, not the original React/Next.js source code or its backend services. Features that depend on the original server, private APIs, forms, analytics, or live data may not work offline.
