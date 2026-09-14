import { createReadStream, existsSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const projectDirectory = path.dirname(fileURLToPath(import.meta.url));
const mirrorName = process.argv[2] ?? 'site-mirror';
if (!/^[a-zA-Z0-9_-]+$/.test(mirrorName)) {
  throw new Error('Mirror directory must be a simple name containing letters, numbers, - or _.');
}
const mirrorRoot = path.join(projectDirectory, mirrorName);
const mainHostRoot = path.join(mirrorRoot, 'www.sammylabs.com');
const port = Number(process.argv[3] ?? process.env.PORT ?? 4173);
const hostDirectories = new Set([
  'api.fontshare.com',
  'cdn.fontshare.com',
  'fonts.googleapis.com',
  'fonts.gstatic.com',
]);
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

const safePath = (root, pathname) => {
  const resolved = path.resolve(root, `.${pathname}`);
  return resolved === root || resolved.startsWith(`${root}${path.sep}`) ? resolved : null;
};

const withScraperQuerySuffix = (filename, searchParams) => {
  const query = searchParams.toString();
  if (!query) return filename;
  const extension = path.extname(filename);
  const stem = extension ? filename.slice(0, -extension.length) : filename;
  return `${stem}_${decodeURIComponent(query)}${extension}`;
};

createServer((request, response) => {
  const requestUrl = new URL(request.url ?? '/', `http://${request.headers.host}`);
  const decodedPath = decodeURIComponent(requestUrl.pathname);
  const firstSegment = decodedPath.split('/').filter(Boolean)[0];
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
    'cache-control': 'no-store',
  });
  createReadStream(filename).pipe(response);
}).listen(port, '127.0.0.1', () => {
  console.log(`SAMMY Labs mirror: http://127.0.0.1:${port}/`);
});
