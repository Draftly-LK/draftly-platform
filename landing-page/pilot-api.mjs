import { createHash } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const metadataTokenUrl = 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token';

/** @param {import('node:http').ServerResponse} response @param {number} status @param {object} body */
function json(response, status, body) {
  response.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' }).end(JSON.stringify(body));
}

/** Create a filesystem-backed pilot request store for local development.
 * @param {string} directory
 */
export function createFilesystemPilotStore(directory) {
  return {
    /** @param {string} id @param {{email: string, receivedAt: string}} record */
    async save(id, record) {
      await mkdir(directory, { recursive: true, mode: 0o700 });
      try {
        await writeFile(path.join(directory, `${id}.json`), `${JSON.stringify(record)}\n`, { flag: 'wx', mode: 0o600 });
      } catch (error) {
        // Retrying an accepted email is idempotent and creates no second request.
        if (!(error instanceof Error && 'code' in error && error.code === 'EEXIST')) throw error;
      }
    },
  };
}

/** Create a private GCS-backed store using the Cloud Run service identity.
 * @param {string} bucket
 * @param {{fetch?: typeof globalThis.fetch, tokenUrl?: string}} [options]
 */
export function createGcsPilotStore(bucket, options = {}) {
  if (!/^[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]$/.test(bucket)) throw new Error('PILOT_GCS_BUCKET is not a valid bucket name.');
  const fetchImpl = options.fetch ?? globalThis.fetch;
  const tokenUrl = options.tokenUrl ?? metadataTokenUrl;
  let token = '';
  let tokenExpiresAt = 0;

  const accessToken = async () => {
    if (token && tokenExpiresAt > Date.now() + 60_000) return token;
    const response = await fetchImpl(tokenUrl, { headers: { 'Metadata-Flavor': 'Google' } });
    if (!response.ok) throw new Error(`Unable to obtain workload access token (${response.status}).`);
    const body = await response.json();
    if (!body || typeof body.access_token !== 'string' || typeof body.expires_in !== 'number') throw new Error('Workload access token response was invalid.');
    token = body.access_token;
    tokenExpiresAt = Date.now() + body.expires_in * 1000;
    return token;
  };

  return {
    /** @param {string} id @param {{email: string, receivedAt: string}} record */
    async save(id, record) {
      const name = encodeURIComponent(`pilot-requests/${id}.json`);
      const url = `https://storage.googleapis.com/upload/storage/v1/b/${encodeURIComponent(bucket)}/o?uploadType=media&ifGenerationMatch=0&name=${name}`;
      const response = await fetchImpl(url, {
        method: 'POST',
        headers: {
          authorization: `Bearer ${await accessToken()}`,
          'content-type': 'application/json; charset=utf-8',
        },
        body: `${JSON.stringify(record)}\n`,
      });
      // The generation precondition makes a repeated email idempotent.
      if (!response.ok && response.status !== 412) throw new Error(`Pilot request upload failed (${response.status}).`);
    },
  };
}

/** Create the intake route. It does not send email or contact a third party.
 * @param {{save(id: string, record: {email: string, receivedAt: string}): Promise<void>}} store
 * @param {{ trustProxy?: boolean }} [options] trustProxy: rate-limit on the last X-Forwarded-For hop (the address the proxy saw) instead of the socket peer.
 */
export function createPilotHandler(store, { trustProxy = false } = {}) {
  /** @type {Map<string, {count: number, reset: number}>} */
  const attempts = new Map();
  /** @param {import('node:http').IncomingMessage} request @param {import('node:http').ServerResponse} response */
  return async function handlePilot(request, response) {
    if (request.method !== 'POST') { response.setHeader('allow', 'POST'); json(response, 405, { code: 'method_not_allowed' }); return; }
    const origin = request.headers.origin;
    try {
      if (origin && new URL(origin).host !== request.headers.host) { json(response, 403, { code: 'origin_rejected' }); return; }
    } catch { json(response, 403, { code: 'origin_rejected' }); return; }
    const now = Date.now();
    for (const [key, value] of attempts) if (value.reset < now) attempts.delete(key);
    const forwarded = trustProxy ? request.headers['x-forwarded-for']?.toString().split(',').at(-1)?.trim() : undefined;
    const ip = forwarded || (request.socket.remoteAddress ?? 'unknown');
    const attempt = attempts.get(ip) ?? { count: 0, reset: now + 60_000 };
    if (++attempt.count > 20) { json(response, 429, { code: 'rate_limited' }); return; }
    attempts.set(ip, attempt);
    let raw = '';
    try {
      for await (const chunk of request) {
        raw += chunk.toString();
        if (Buffer.byteLength(raw) > 4096) { json(response, 413, { code: 'request_too_large' }); return; }
      }
      const type = request.headers['content-type']?.split(';')[0];
      /** @type {unknown} */
      const input = type === 'application/json' ? JSON.parse(raw) : type === 'application/x-www-form-urlencoded' ? Object.fromEntries(new URLSearchParams(raw)) : null;
      if (!input || typeof input !== 'object' || !('email' in input) || typeof input.email !== 'string') {
        json(response, 400, { code: 'invalid_email' }); return;
      }
      const email = input.email.trim().toLowerCase();
      if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { json(response, 400, { code: 'invalid_email' }); return; }
      const id = createHash('sha256').update(email).digest('hex');
      await store.save(id, { email, receivedAt: new Date().toISOString() });
      json(response, 200, { accepted: true });
    } catch (error) {
      json(response, error instanceof SyntaxError ? 400 : 503, { code: error instanceof SyntaxError ? 'invalid_request' : 'storage_unavailable' });
    }
  };
}
