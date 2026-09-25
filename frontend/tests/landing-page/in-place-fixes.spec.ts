import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const evidence = path.resolve(process.cwd(), '../docs/review/landing-page/2026-09-21/in-place-fix');

test('preserves the animated landing page while applying the scoped content fixes', async ({ page, request }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await expect(page.locator('main h1')).toContainText('review-ready matter');
  await expect(page.locator('.draftly-intro-panel')).toBeVisible();
  await expect(page.locator('[data-draftly-scope]')).toContainText('Sri Lanka');
  await expect(page.getByText('GLOBAL REGULATORY COVERAGE', { exact: false })).toHaveCount(0);
  await expect(page.getByText(/SAMMY/i)).toHaveCount(0);
  expect(await page.locator('main span').count()).toBeGreaterThan(1_000);
  expect(await page.locator('.draftly-intro-panel').evaluate((element) => getComputedStyle(element).backgroundColor)).toBe('rgba(20, 19, 20, 0.8)');
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);

  await mkdir(evidence, { recursive: true });
  await page.screenshot({ path: path.join(evidence, 'desktop-hero.png') });
  await page.locator('[data-draftly-scope]').scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(evidence, 'desktop-sri-lanka-scope.png') });

  for (const route of ['/careers', '/regulators', '/privacy-policy', '/terms', '/dpa', '/subprocessors', '/security', '/service-description']) {
    expect((await request.get(route)).status(), route).toBe(404);
  }
  expect((await request.get('/favicon.ico')).status()).toBe(200);
  expect(errors).toEqual([]);
});

test('keeps the audience cards clean after switching tabs and returning to the page', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  const chipRows = page.locator('div.flex.flex-wrap.gap-1\\.5');
  const audienceTabs = ['Legal teams and institutions', 'Researchers and public-interest partners', 'Conveyancing practices'];

  for (const name of audienceTabs) {
    await page.getByRole('button', { name: new RegExp(name, 'i') }).click();
    // React re-renders the cards from their original data; the fixes must reapply.
    await expect.poll(async () => page.locator('main').evaluate((main) => /Â|\+\d{2,3}$/m.test((main as HTMLElement).innerText))).toBe(false);
  }

  const expected = ['Deeds', 'Plans', 'Registry records', 'Assessments', 'Title reports'];
  await expect.poll(async () => chipRows.first().locator('span').allTextContents()).toEqual(expected);
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await expect.poll(async () => chipRows.first().locator('span').allTextContents()).toEqual(expected);
  await expect(page.getByText(/ \? /)).toHaveCount(0);
});

test('keeps the same fixes usable on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/');
  await expect(page.locator('main h1')).toContainText('review-ready matter');
  await expect(page.locator('.draftly-intro-panel')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  await mkdir(evidence, { recursive: true });
  await page.screenshot({ path: path.join(evidence, 'mobile-hero.png') });
  await page.locator('[data-draftly-scope]').scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(evidence, 'mobile-sri-lanka-scope.png') });
});
