import { expect, test } from '@playwright/test';
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';

const evidence = path.resolve(process.cwd(), '../docs/review/landing-page/2026-09-18');
const email = 'draftly-pilot-test@example.test';

for (const viewport of [{ width: 375, height: 812 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
  test(`render and navigation ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    const failed: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('response', (response) => { if (response.status() >= 400) failed.push(`${response.status()} ${response.url()}`); });
    await page.goto('/');
    await expect(page.locator('main h1')).toContainText('review-ready matter');
    await expect(page.getByText('WHAT DRAFTLY DOES', { exact: true })).toBeVisible();
    await expect(page.getByText('WHAT DRAFTLY DOESz', { exact: true })).toHaveCount(0);
    await page.waitForTimeout(1800);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
    const clipped = await page.locator('h1,h2,h3,button,input').evaluateAll((elements) => elements.filter((element) => element.clientWidth && element.scrollWidth > element.clientWidth + 2).map((element) => element.textContent));
    expect(clipped).toEqual([]);
    if (viewport.width < 1024) {
      await page.getByRole('button', { name: 'Open menu' }).click();
      await expect(page.getByRole('dialog')).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog')).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Open menu' })).toBeFocused();
    }
    for (const target of ['Overview', 'Document processing', 'Workflow', 'Trust', 'Request a pilot']) {
      await page.getByRole('button', { name: target, exact: true }).click();
      const y = await page.evaluate(() => window.scrollY);
      expect(y).toBeGreaterThan(0);
    }
    const navTargets = [{ label: 'PRODUCT', id: 'use-cases' }, { label: 'WORKFLOW', id: 'industries' }, { label: 'TRUST', id: 'security' }, { label: 'ABOUT', id: 'get-started' }];
    for (const target of navTargets) {
      if (viewport.width < 1024) await page.getByRole('button', { name: 'Open menu' }).click();
      await page.getByRole('link', { name: target.label, exact: true }).filter({ visible: true }).first().click();
      await expect(page.locator(`#${target.id}`)).toBeInViewport();
    }
    await page.locator('footer').scrollIntoViewIfNeeded();
    await mkdir(evidence, { recursive: true });
    await page.screenshot({ path: path.join(evidence, `footer-${viewport.width}x${viewport.height}.png`) });
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => { const active = document.activeElement; return active && getComputedStyle(active).outlineStyle !== 'none'; })).toBeTruthy();
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(700);
    await mkdir(evidence, { recursive: true });
    await page.screenshot({ path: path.join(evidence, `final-${viewport.width}x${viewport.height}.png`) });
    await writeFile(path.join(evidence, `audit-${viewport.width}x${viewport.height}.json`), JSON.stringify({ viewport, errors, failed, clipped }, null, 2));
    expect(errors).toEqual([]);
    expect(failed).toEqual([]);
  });
}

test('research links, footer routes, and beta CTA reach their destinations', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('response', (response) => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
  await page.goto('/');
  await expect(page.locator('main h1')).toBeVisible();
  await page.getByRole('link', { name: 'EXPLORE THE RESEARCH', exact: true }).click();
  await expect(page).toHaveURL(/\/lab$/);
  await expect(page.locator('h1')).toContainText('Sri Lankan legal material');
  await page.goto('/');
  await expect(page.locator('main h1')).toBeVisible();
  await page.getByRole('link', { name: 'RESEARCH', exact: true }).filter({ visible: true }).first().click();
  await expect(page).toHaveURL(/\/lab$/);
  await page.goto('/');
  await expect(page.locator('main h1')).toBeVisible();
  const links = await page.locator('footer a').evaluateAll((elements) => elements.map((element) => element.getAttribute('href')).filter((href): href is string => !!href));
  for (const href of new Set(links)) {
    if (href.includes('#')) continue;
    const response = await request.get(href);
    expect(response.ok(), href).toBeTruthy();
    await page.goto(href);
    await expect(page.locator('body')).not.toBeEmpty();
    await page.waitForTimeout(500);
  }
  expect(errors).toEqual([]);
  const redirect = await request.get('/app', { maxRedirects: 0 });
  expect(redirect.status()).toBe(302);
  expect(redirect.headers().location).toBe('http://127.0.0.1:4310/');
  await page.goto('/');
  await expect(page.locator('main h1')).toBeVisible();
  await page.getByRole('link', { name: 'TRY DRAFTLY BETA' }).click();
  await expect(page).toHaveURL(/127\.0\.0\.1:4310/);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/');
  await expect(page.locator('main h1')).toBeVisible();
  await page.getByRole('button', { name: 'Open menu' }).click();
  await page.getByRole('link', { name: 'TRY BETA', exact: true }).click();
  await expect(page).toHaveURL(/127\.0\.0\.1:4310/);
});

test('pilot validation, submitting, server error, network error and durable success', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'REQUEST A PILOT', exact: true }).click();
  const input = page.getByRole('textbox', { name: 'Work email' });
  await expect(input).toBeFocused();
  await input.fill('invalid');
  await page.getByRole('button', { name: 'SEND REQUEST' }).click();
  await expect(page.locator('form').getByRole('alert')).toContainText('required fields');
  await input.fill(email);
  await page.route('**/api/pilot-requests', (route) => route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }));
  await page.getByRole('button', { name: 'SEND REQUEST' }).click();
  await expect(page.locator('form').getByRole('alert')).toContainText('Please try again');
  await page.unroute('**/api/pilot-requests');
  await page.route('**/api/pilot-requests', (route) => route.abort('failed'));
  await page.getByRole('button', { name: 'SEND REQUEST' }).click();
  await expect(page.locator('form').getByRole('alert')).toContainText('Check your connection');
  await page.unroute('**/api/pilot-requests');
  let count = 0;
  let release: (() => void) | undefined;
  const hold = new Promise<void>((resolve) => { release = resolve; });
  await page.route('**/api/pilot-requests', async (route) => { count++; await hold; await route.continue(); });
  const response = page.waitForResponse((response) => response.url().endsWith('/api/pilot-requests') && response.status() === 200);
  await page.getByRole('button', { name: 'SEND REQUEST' }).click();
  await expect(page.getByRole('button', { name: 'SENDING…' })).toBeDisabled();
  await expect(input).toBeDisabled();
  await page.locator('form').evaluate((form) => form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  release?.();
  const accepted = await response;
  expect(await accepted.json()).toEqual({ accepted: true });
  expect(JSON.parse(accepted.request().postData() ?? '{}')).toEqual({ email });
  await expect(page.getByRole('status')).toContainText('Request received');
  expect(count).toBe(1);
  const id = createHash('sha256').update(email).digest('hex');
  const directory = path.resolve(process.cwd(), '../landing-page/.local/pilot-requests');
  expect(JSON.parse(await readFile(path.join(directory, `${id}.json`), 'utf8')).email).toBe(email);
  expect((await readdir(directory)).filter((file) => file === `${id}.json`)).toHaveLength(1);
});

test('pilot API rejects invalid requests and accepts retries idempotently', async ({ request }) => {
  expect((await request.get('/api/pilot-requests')).status()).toBe(405);
  expect((await request.post('/api/pilot-requests', { data: { email: 'invalid' } })).status()).toBe(400);
  expect((await request.post('/api/pilot-requests', { headers: { Origin: 'https://example.test' }, data: { email } })).status()).toBe(403);
  expect((await request.post('/api/pilot-requests', { data: { email } })).status()).toBe(200);
  expect((await request.post('/api/pilot-requests', { data: { email } })).status()).toBe(200);
});
