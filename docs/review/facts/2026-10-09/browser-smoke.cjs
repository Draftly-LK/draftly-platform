// Synthetic browser review. Start the local API-mode frontend with a test token
// adapter, never a production auth change. Backend persistence is tested separately.
const { chromium, expect } = require('../../../../frontend/node_modules/@playwright/test');
const AxeBuilder = require('../../../../frontend/node_modules/@axe-core/playwright').default;
const fs = require('node:fs');
const path = require('node:path');
const pageInfo = { limit: 50, hasMore: false, nextCursor: null };
const original = {
  id: 'synthetic-fact', matterId: 'mat-1', factTypeId: 'rta.party.holder_name_en',
  fieldKey: 'holderNameEn', labelKey: 'rta.fact.holder_name_en',
  value: 'SYNTHETIC DOCUMENT HOLDER', originalValue: 'SYNTHETIC DOCUMENT HOLDER',
  status: 'EXTRACTED_CANDIDATE', origin: 'machine', modelReportedConfidence: 0.81,
  evidence: [{ id: 'synthetic-evidence', sourceFileId: 'source', detectedDocumentId: 'doc',
    pageNumber: 1, sourceSha256: 'a'.repeat(64), extractionRunId: 'run',
    supportingText: 'SYNTHETIC DOCUMENT HOLDER', pageText: 'SYNTHETIC DOCUMENT HOLDER page',
    precision: 'text', candidateId: null, candidateVersion: null, boundingBox: null }],
  reviewedBy: null, reviewedAt: null, createdAt: '2026-10-09T00:00:00Z', version: 1,
  transactionId: null, subjectId: null, scopeStatus: 'unassigned', evidenceStale: false,
  sourceCandidateId: 'synthetic-candidate', manualReason: null, lineageId: 'synthetic-lineage',
  supersedesFactId: null, supersededByFactId: null, scopeToken: 'synthetic-token-1', conflictFactIds: []
};
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: false, args: ['--remote-debugging-port=9225'] });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    const errors = [], commands = [], audits = [], history = [original], decisions = [];
    let current = original;
    page.on('pageerror', e => errors.push(String(e)));
    await page.route('http://api.test/**', async route => {
      const req = route.request(), url = new URL(req.url()), pathname = url.pathname;
      let body = { items: [], page: pageInfo }, status = 200;
      if (req.method() !== 'OPTIONS') {
        if (pathname === '/api/v1/me') body = { id: 'synthetic-lawyer', displayName: 'Synthetic reviewer', role: 'approver' };
        else if (pathname === '/api/v1/matters/mat-1') body = { id: 'mat-1', reference: 'SYNTHETIC ACCEPTANCE REVIEW', state: 'EVIDENCE_COLLECTION', version: 1, partyContexts: [] };
        else if (pathname.endsWith('/fact-types')) body = { versions: {}, factTypes: [{ id: original.factTypeId, labelKey: original.labelKey, fieldKey: original.fieldKey, subject: 'PARTY', valueKind: 'TEXT', critical: false, negativeRequiresSearchEvidence: false }] };
        else if (pathname.endsWith('/source-files')) body = { items: [{ id: 'source', matterId: 'mat-1', originalFilename: 'Synthetic source.pdf', sha256: 'a'.repeat(64), pageCount: 1, state: 'PROCESSED', detectedDocumentIds: ['doc'] }], page: pageInfo };
        else if (req.method() === 'POST' && /\/(accept|correct)$/.test(pathname)) {
          const requestBody = req.postDataJSON();
          commands.push({ path: pathname, body: requestBody, version: req.headers()['if-match'], key: req.headers()['idempotency-key'] });
          expect(req.headers()['if-match']).toBe(`"${current.version}"`);
          expect(requestBody).not.toHaveProperty('subjectId');
          expect(requestBody).not.toHaveProperty('transactionId');
          const previous = current;
          current = { ...previous, id: previous.id + '-next', version: previous.version + 1,
            value: requestBody.value ?? previous.value, status: 'LAWYER_CONFIRMED',
            scopeToken: 'synthetic-token-' + (previous.version + 1),
            supersedesFactId: previous.id, reviewedBy: 'synthetic-lawyer', reviewedAt: '2026-10-09T00:00:00Z' };
          history.push(current);
          decisions.push({ id: 'decision-' + current.version, decision: pathname.split('/').at(-1), targetId: current.id, reviewerId: 'synthetic-lawyer', reviewerRole: 'approver', createdAt: current.reviewedAt, previousValue: previous.value, newValue: current.value, reason: requestBody.reason ?? null, resolvedFactIds: [] });
          body = current;
        } else if (pathname.endsWith('/history')) body = { items: history, decisions, page: pageInfo };
        else if (pathname === '/api/v1/matters/mat-1/facts') body = { items: [current], page: pageInfo };
        else if (pathname.startsWith('/api/v1/matters/mat-1/facts/')) body = current;
      }
      await route.fulfill({ status, contentType: 'application/json', headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type, Authorization, Idempotency-Key, If-Match' }, body: JSON.stringify(body) });
    });
    async function audit(state) {
      const report = await new AxeBuilder({ page }).include('main').analyze();
      const violations = report.violations.filter(v => ['critical', 'serious'].includes(v.impact));
      audits.push({ state, seriousCritical: violations.map(v => v.id) });
      expect(violations).toEqual([]);
    }
    await page.goto('http://127.0.0.1:4316/matters/mat-1/facts', { waitUntil: 'domcontentloaded', timeout: 180000 });
    await expect(page.getByRole('button', { name: 'Accept', exact: true })).toBeVisible({ timeout: 60000 });
    await expect(page.getByLabel('Reason for this decision')).toHaveCount(0);
    await audit('before-accept');
    await page.screenshot({ path: path.join(__dirname, 'before-accept.png') });
    await page.getByRole('button', { name: 'Accept', exact: true }).click();
    await expect(page.getByText('Lawyer confirmed', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Reason for this decision')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Accept', exact: true })).toHaveCount(0);
    expect(commands).toHaveLength(1);
    expect(current.scopeStatus).toBe('unassigned');
    await page.reload();
    await expect(page.getByText('Lawyer confirmed', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Review or correct' }).click();
    await expect(page.getByLabel('Corrected value')).toBeEnabled();
    await page.getByLabel('Corrected value').fill('SYNTHETIC CORRECTED HOLDER');
    await page.getByLabel('Reason for this decision').fill('Synthetic source re-read');
    await page.getByRole('button', { name: 'Save correction' }).click();
    await expect(page.getByLabel('Corrected value')).toHaveValue('SYNTHETIC CORRECTED HOLDER');
    await expect(page.getByText('Synthetic source re-read', { exact: true })).toBeVisible();
    expect(commands.map(c => c.path.split('/').at(-1))).toEqual(['accept', 'correct']);
    await audit('after-correction');
    await page.getByRole('button', { name: 'Close', exact: true }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(600);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: path.join(__dirname, 'accepted-mobile.png') });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(__dirname, 'accepted-desktop.png') });
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.waitForTimeout(600);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: path.join(__dirname, 'accepted-1024.png') });
    expect(errors).toEqual([]);
    fs.writeFileSync(path.join(__dirname, 'browser-results.json'), JSON.stringify({ synthetic: true, backend: 'stateful API fixture; separate real PostgreSQL contract suite', oneClickAccept: true, confirmedAfterReload: true, correctionWithReason: true, mobileOverflow: false, audits, pageErrors: errors, commands }, null, 2));
    console.log('Browser verification passed; holding Chrome for DevTools inspection for 60 seconds.');
    await page.waitForTimeout(60000);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
