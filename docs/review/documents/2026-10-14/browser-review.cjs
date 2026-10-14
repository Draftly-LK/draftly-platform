const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { createRequire } = require('node:module');
require = createRequire(path.resolve('package.json'));
const { chromium } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const viteDir = path.dirname(require.resolve('vite/package.json', { paths: [path.dirname(require.resolve('vitest/package.json'))] }));
const esbuild = require(require.resolve('esbuild', { paths: [viteDir] }));
const out = path.resolve('../docs/review/documents/2026-10-14');
const checklist = require('./src/test/fixtures/requirement-readiness.json').original.checklist;
const inbox = { matterId: 'mat_synthetic', sourceFiles: [1, 2, 3].map(n => ({ id: `synthetic-source-${n}`, originalFilename: `SYNTHETIC evidence ${n}.pdf`, state: 'STORED', pageCount: 2 })), documents: [{ id: 'synthetic-doc', classId: null, boundaryStatus: 'CONFIRMED', extractionState: 'refresh_required', spansMultipleSources: false, fragments: [{ sourceFileId: 'synthetic-source-1', pageStart: 1, pageEnd: 2 }] }], unprocessedSourceFileIds: ['synthetic-source-1', 'synthetic-source-2', 'synthetic-source-3'], boundaryReviewDocumentIds: [], classificationReviewDocumentIds: [], unidentifiedDocumentIds: ['synthetic-doc'], pageAccounting: [], page: { hasMore: false, nextCursor: null } };
(async () => {
  const bundle = await esbuild.build({ stdin: { contents: `import React from 'react';import {createRoot} from 'react-dom/client';import {NextIntlClientProvider} from 'next-intl';import {DocumentsScreen} from './src/components/matter/documents-screen';import en from './src/lib/i18n/messages/en.json';import si from './src/lib/i18n/messages/si.json';const locale=new URLSearchParams(location.search).get('locale')||'en';document.documentElement.lang=locale;createRoot(document.getElementById('root')).render(<NextIntlClientProvider locale={locale} messages={locale==='si'?si:en} timeZone="Asia/Colombo"><DocumentsScreen matterId="mat_synthetic"/></NextIntlClientProvider>);`, resolveDir: process.cwd(), loader: 'tsx' }, bundle: true, write: false, format: 'iife', platform: 'browser', jsx: 'automatic', tsconfig: 'tsconfig.json', define: { 'process.env.NODE_ENV': '"production"', 'process.env.NEXT_PUBLIC_API_BASE_URL': '"http://synthetic.local"' }, plugins: [{ name: 'preview', setup(build) {
    build.onLoad({ filter: /use-token-provider\.ts$/ }, () => ({ contents: 'const token=async()=>null;export const useTokenProvider=()=>token;', loader: 'ts' }));
    build.onLoad({ filter: /app-shell\.tsx$/ }, () => ({ contents: 'export function AppShell({children}){return <main>{children}</main>}', loader: 'tsx' }));
    build.onLoad({ filter: /lib[\\/]api[\\/]documents\.ts$/ }, () => ({ contents: `export const getCompleteDocumentInbox=async()=>(${JSON.stringify(inbox)});export const uploadSourceFile=async()=>{};export const createDocumentGroup=async()=>{};export const getDetectedDocument=async()=>{};export const recordPageDisposition=async()=>{};`, loader: 'ts' }));
    build.onLoad({ filter: /lib[\\/]api[\\/]matters\.ts$/ }, () => ({ contents: `export const getChecklist=async()=>(${JSON.stringify(checklist)});`, loader: 'ts' }));
    build.onResolve({ filter: /^next\/link$/ }, a => ({ path: a.path, namespace: 'preview' }));
    build.onLoad({ filter: /.*/, namespace: 'preview' }, () => ({ contents: 'export default function Link({children,...props}){return <a {...props}>{children}</a>}', loader: 'jsx', resolveDir: process.cwd() }));
  } }] });
  const server = http.createServer((req, res) => {
    if (req.url === '/bundle.js') { res.setHeader('Content-Type', 'application/javascript'); return res.end(bundle.outputFiles[0].text); }
    if (req.url === '/preview.css') { res.setHeader('Content-Type', 'text/css'); return res.end(fs.readFileSync(path.join(out, 'preview.css'))); }
    res.setHeader('Content-Type', 'text/html'); res.end('<!doctype html><html><head><title>Synthetic documents preview</title><link rel="stylesheet" href="/preview.css"></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>');
  });
  await new Promise(resolve => server.listen(4399, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage(); const errors = []; const results = [];
  page.on('pageerror', e => errors.push(e.message));
  try {
    for (const locale of ['en', 'si']) for (const width of [1440, 1024]) {
      await page.setViewportSize({ width, height: width === 1440 ? 900 : 768 });
      await page.goto(`http://127.0.0.1:4399/?locale=${locale}`);
      const panel = page.locator('main > div > div > details').first();
      await panel.waitFor();
      if (await panel.getAttribute('open') !== null) throw new Error('Requirements should start collapsed');
      const summary = panel.locator('summary').first();
      await summary.focus(); await page.keyboard.press('Enter');
      if (await panel.getAttribute('open') === null) throw new Error('Keyboard expansion failed');
      await page.screenshot({ path: path.join(out, `expanded-${locale}-${width}.png`), fullPage: true });
      const expanded = await new AxeBuilder({ page }).analyze();
      await summary.focus(); await page.keyboard.press('Space');
      if (await panel.getAttribute('open') !== null) throw new Error('Keyboard collapse failed');
      const order = await page.evaluate(() => { const details = document.querySelector('main details'); return [...document.querySelectorAll('main table')].every(table => Boolean(table.compareDocumentPosition(details) & Node.DOCUMENT_POSITION_FOLLOWING)); });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      const serious = expanded.violations.filter(v => ['serious', 'critical'].includes(v.impact)).map(v => v.id);
      results.push({ locale, width, tablesBeforeRequirements: order, overflow, serious });
      await page.screenshot({ path: path.join(out, `collapsed-${locale}-${width}.png`), fullPage: true });
      if (!order || overflow || serious.length) throw new Error(JSON.stringify(results.at(-1)));
    }
    fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify({ synthetic: true, scope: 'Real DocumentsScreen and RequirementsPanel; synthetic inbox and checklist; shell omitted', results, errors }, null, 2));
    console.log(JSON.stringify({ results, errors }));
    if (errors.length) throw new Error('Browser errors');
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
