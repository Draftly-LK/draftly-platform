/**
 * `Cache-Control` for a served file. Kept separate from `serve.mjs` (which
 * binds a port at import time) so it can be unit-tested directly, the same
 * way `pilot-api.mjs` is.
 *
 * Webpack chunk and CSS filenames under `_next/static/` (and the two icon
 * files) carry a content hash, so a change always lands at a new URL: those
 * are safe to cache for a year. HTML is revalidated every time, so a content
 * edit is never stuck behind a cache. Everything else (the favicon,
 * `draftly-fixes.js`, the fonts) is not hash-named and can change in place on
 * a redeploy, so it gets a short cache instead of `immutable`.
 * @param {string} filename
 */
export const cacheControlFor = (filename) => {
  if (filename.endsWith('.html')) return 'no-store';
  const normalizedFilename = filename.replaceAll('\\', '/');
  const isFingerprinted =
    normalizedFilename.includes('/_next/static/') || /_[0-9a-f]{8,}\.[a-z0-9]+$/i.test(normalizedFilename);
  return isFingerprinted ? 'public, max-age=31536000, immutable' : 'public, max-age=300, must-revalidate';
};
