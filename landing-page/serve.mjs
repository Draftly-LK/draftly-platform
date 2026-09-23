import { createReadStream, existsSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { cacheControlFor } from './cache-policy.mjs';
import { createFilesystemPilotStore, createGcsPilotStore, createPilotHandler } from './pilot-api.mjs';

const projectDirectory = path.dirname(fileURLToPath(import.meta.url));
const mirrorName = process.argv[2] ?? 'site-mirror';
if (!/^[a-zA-Z0-9_-]+$/.test(mirrorName)) {
  throw new Error('Mirror directory must be a simple name containing letters, numbers, - or _.');
}
const mirrorRoot = path.join(projectDirectory, mirrorName);
const mainHostRoot = path.join(mirrorRoot, 'www.sammylabs.com');
const port = Number(process.argv[3] ?? process.env.PORT ?? 4173);
const appUrl = new URL(process.env.DRAFTLY_APP_URL ?? 'http://127.0.0.1:4310/');
if (!['http:', 'https:'].includes(appUrl.protocol) || appUrl.username || appUrl.password) throw new Error('DRAFTLY_APP_URL must be an HTTP(S) application URL without credentials.');
const pilotStore = process.env.PILOT_GCS_BUCKET
  ? createGcsPilotStore(process.env.PILOT_GCS_BUCKET)
  : createFilesystemPilotStore(process.env.PILOT_REQUESTS_DIR ?? path.join(projectDirectory, '.local', 'pilot-requests'));
// Behind a reverse proxy (Caddy) every socket peer is the proxy, so the rate
// limit has to key on the client address it forwards. Off unless asked for.
const handlePilot = createPilotHandler(pilotStore, { trustProxy: process.env.TRUST_PROXY === '1' });
const hostDirectories = new Set([
  'api.fontshare.com',
  'cdn.fontshare.com',
  'fonts.googleapis.com',
  'fonts.gstatic.com',
]);
const unavailableRoutes = new Set([
  'ascii-letter',
  'ascii-magnifying-glass',
  'ascii-phone',
  'ascii-policies',
  'ascii-radar',
  'careers',
  'dpa',
  'lady-justice-v5',
  'lady-justice-v6',
  'privacy-policy',
  'regulators',
  'security',
  'service-description',
  'subprocessors',
  'terms',
]);
/** @type {Map<string, string>} */
const mimeTypes = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml'],
  ['.ttf', 'font/ttf'],
  ['.woff', 'font/woff'],
  ['.woff2', 'font/woff2'],
]);

/** @param {string} root @param {string} pathname */
const safePath = (root, pathname) => {
  const resolved = path.resolve(root, `.${pathname}`);
  return resolved === root || resolved.startsWith(`${root}${path.sep}`) ? resolved : null;
};

/** @param {string} filename @param {URLSearchParams} searchParams */
const withScraperQuerySuffix = (filename, searchParams) => {
  const query = searchParams.size === 1 && [...searchParams.values()][0] === '' ? [...searchParams.keys()][0] : searchParams.toString();
  if (!query) return filename;
  const extension = path.extname(filename);
  const stem = extension ? filename.slice(0, -extension.length) : filename;
  return `${stem}_${decodeURIComponent(query)}${extension}`;
};

createServer((request, response) => {
  let requestUrl;
  let decodedPath;
  try {
    requestUrl = new URL(request.url ?? '/', 'http://127.0.0.1');
    decodedPath = decodeURIComponent(requestUrl.pathname);
  } catch {
    response.writeHead(400).end('Bad request'); return;
  }
  if (decodedPath === '/api/pilot-requests') {
    void handlePilot(request, response).catch(() => response.writeHead(500).end()); return;
  }
  if (decodedPath === '/app') {
    response.writeHead(302, { location: appUrl.href, 'cache-control': 'no-store' }).end(); return;
  }
  const firstSegment = decodedPath.split('/').filter(Boolean)[0];
  if (unavailableRoutes.has(firstSegment)) {
    response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' }).end('Not found'); return;
  }
  if (decodedPath === '/favicon.ico') decodedPath = '/draftly-favicon.svg';
  const root = hostDirectories.has(firstSegment) ? mirrorRoot : mainHostRoot;
  let filename = safePath(root, decodedPath);

  if (!filename) {
    response.writeHead(400).end('Bad request');
    return;
  }
  if (existsSync(filename) && statSync(filename).isDirectory()) {
    filename = path.join(filename, 'index.html');
  }
  if (!existsSync(filename) && requestUrl.search) {
    const suffixed = withScraperQuerySuffix(filename, requestUrl.searchParams);
    if (existsSync(suffixed)) filename = suffixed;
  }
  if (!existsSync(filename)) {
    response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' }).end('Not found');
    return;
  }

  response.writeHead(200, {
    'content-type': mimeTypes.get(path.extname(filename).toLowerCase()) ?? 'application/octet-stream',
    'cache-control': cacheControlFor(filename),
  });
  createReadStream(filename).pipe(response);
}).listen(port, process.env.HOST ?? '0.0.0.0', () => {
  console.log(`Draftly landing page listening on port ${port}.`);
});
