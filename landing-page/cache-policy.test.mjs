import assert from 'node:assert/strict';
import test from 'node:test';

import { cacheControlFor } from './cache-policy.mjs';

test('HTML pages are never cached, so a content edit is never stuck behind one', () => {
  assert.equal(cacheControlFor('/app/site-mirror/www.sammylabs.com/index.html'), 'no-store');
});

test('content-hashed webpack output is cached for a year as immutable', () => {
  assert.equal(
    cacheControlFor('/app/site-mirror/www.sammylabs.com/_next/static/chunks/116-1175d20e23071689_dpl=x.js'),
    'public, max-age=31536000, immutable',
  );
  assert.equal(
    cacheControlFor('/app/site-mirror/www.sammylabs.com/_next/static/css/7d5725afb220b397_dpl=x.css'),
    'public, max-age=31536000, immutable',
  );
});

test('a hash-suffixed filename outside _next/static is also treated as fingerprinted', () => {
  assert.equal(
    cacheControlFor('/app/site-mirror/www.sammylabs.com/icon_4888f70e48b8b565.png'),
    'public, max-age=31536000, immutable',
  );
});

test('a filename with no content hash gets a short cache, since it can change in place', () => {
  assert.equal(cacheControlFor('/app/site-mirror/www.sammylabs.com/draftly-favicon.svg'), 'public, max-age=300, must-revalidate');
  assert.equal(cacheControlFor('/app/site-mirror/www.sammylabs.com/draftly-fixes.js'), 'public, max-age=300, must-revalidate');
  assert.equal(
    cacheControlFor('/app/site-mirror/www.sammylabs.com/fonts/PerfectlyNineties-Regular.woff2'),
    'public, max-age=300, must-revalidate',
  );
});

test('a short run of digits is not mistaken for a content hash', () => {
  assert.equal(cacheControlFor('/app/site-mirror/www.sammylabs.com/foo123.png'), 'public, max-age=300, must-revalidate');
});
