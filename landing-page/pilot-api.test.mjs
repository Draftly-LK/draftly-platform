import assert from 'node:assert/strict';
import test from 'node:test';

import { createGcsPilotStore } from './pilot-api.mjs';

test('GCS store uses workload identity and an idempotent object upload', async () => {
  const calls = [];
  const fetch = async (url, init = {}) => {
    calls.push({ url: String(url), init });
    if (String(url).startsWith('http://metadata.test/')) {
      return new globalThis.Response(JSON.stringify({ access_token: 'test-token', expires_in: 3600 }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    }
    return new globalThis.Response('{}', { status: 200 });
  };

  const store = createGcsPilotStore('draftly-pilot-preview', {
    fetch,
    tokenUrl: 'http://metadata.test/token',
  });
  await store.save('abc123', { email: 'pilot@example.com', receivedAt: '2026-09-21T00:00:00.000Z' });

  assert.equal(calls.length, 2);
  assert.equal(calls[0].init.headers['Metadata-Flavor'], 'Google');
  assert.match(calls[1].url, /ifGenerationMatch=0/);
  assert.match(calls[1].url, /name=pilot-requests%2Fabc123.json/);
  assert.equal(calls[1].init.headers.authorization, 'Bearer test-token');
});

test('GCS store treats a generation precondition failure as an accepted duplicate', async () => {
  const fetch = async (url) => String(url).startsWith('http://metadata.test/')
    ? new globalThis.Response(JSON.stringify({ access_token: 'test-token', expires_in: 3600 }), { status: 200 })
    : new globalThis.Response('', { status: 412 });
  const store = createGcsPilotStore('draftly-pilot-preview', {
    fetch,
    tokenUrl: 'http://metadata.test/token',
  });

  await assert.doesNotReject(store.save('abc123', { email: 'pilot@example.com', receivedAt: '2026-09-21T00:00:00.000Z' }));
});
