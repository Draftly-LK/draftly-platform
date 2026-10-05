import { expect, test } from '@playwright/test';

declare global {
  interface Window {
    navbarEntrances: number[];
  }
}

for (const viewport of [{ width: 1440, height: 900 }, { width: 375, height: 812 }]) {
  test(`navbar enters once per load at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.addInitScript(() => {
      const trace = window;
      trace.navbarEntrances = [];
      document.addEventListener('animationstart', (event) => {
        if (event.animationName !== 'node-content-in' || !(event.target instanceof Element)) return;
        const link = event.target.closest('a');
        const nav = link?.closest('nav');
        if (!nav || !['', '/'].includes(link?.getAttribute('href') ?? 'missing')) return;
        const bounds = nav.getBoundingClientRect();
        if (bounds.width && bounds.height && getComputedStyle(nav).visibility === 'visible') {
          trace.navbarEntrances.push(performance.now());
        }
      });
    });

    let releaseBoot!: () => void;
    let bootReady: Promise<void>;
    await page.route('**/_next/static/chunks/116-*', async (route) => {
      await bootReady;
      await route.continue();
    });

    for (const load of ['cold', 'reload']) {
      bootReady = new Promise<void>((resolve) => { releaseBoot = resolve; });
      if (load === 'cold') await page.goto('/', { waitUntil: 'domcontentloaded' });
      else await page.reload({ waitUntil: 'domcontentloaded' });

      // Simulate slow JavaScript without a fixed delay: let the saved navbar's
      // wordmark animation finish before releasing the client bootstrap.
      await page.waitForFunction(() => [...document.querySelectorAll('nav a')].some((link) =>
        link.getAnimations().some((animation) => animation instanceof CSSAnimation &&
          animation.animationName === 'node-content-in' && animation.playState === 'finished'),
      ));
      releaseBoot();
      await expect(page.locator('main h1')).toContainText('review-ready matter');
      await expect(page.getByRole('link', { name: 'Draftly', exact: true }).first().locator('span')).toBeVisible();
      expect(await page.evaluate(() => window.navbarEntrances.length), load).toBe(1);
    }

    const background = page.locator('nav:visible').first().locator('..').locator('.backdrop-blur-xl');
    await expect(background).toHaveCSS('background-color', 'rgba(20, 19, 20, 0.75)');
    for (const [id, color] of [
      ['industries', 'rgba(255, 255, 255, 0.75)'],
      ['use-cases', 'rgba(20, 19, 20, 0.75)'],
    ] as const) {
      await page.evaluate((sectionId) => {
        const section = document.getElementById(sectionId)!;
        window.scrollTo({ top: window.scrollY + section.getBoundingClientRect().top + 200, behavior: 'instant' });
      }, id);
      await expect(background).toHaveCSS('background-color', color);
    }
    if (viewport.width < 1024) {
      await page.getByRole('button', { name: 'Open menu' }).click();
      await expect(page.getByRole('dialog')).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog')).toHaveCount(0);
    }
  });
}

test('navbar backdrop follows the section theme rather than repaired label colours', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto('/');
  await expect(page.locator('main h1')).toContainText('review-ready matter');
  const nav = page.locator('nav:visible').first();
  await expect(nav).toHaveCSS('background-color', 'rgba(20, 19, 20, 0.72)');

  // Contrast repairs can change text independently of React's section theme.
  await nav.locator('a > span').first().evaluate((label) => {
    (label as HTMLElement).style.setProperty('color', '#475569', 'important');
    window.dispatchEvent(new Event('resize'));
  });
  await expect(nav).toHaveCSS('background-color', 'rgba(20, 19, 20, 0.72)');
  for (const [id, color] of [
    ['industries', 'rgba(255, 251, 245, 0.86)'],
    ['use-cases', 'rgba(20, 19, 20, 0.72)'],
  ] as const) {
    await page.evaluate((sectionId) => {
      const section = document.getElementById(sectionId)!;
      window.scrollTo({ top: window.scrollY + section.getBoundingClientRect().top + 200, behavior: 'instant' });
    }, id);
    await expect(nav).toHaveCSS('background-color', color);
  }
});

test('saved navbar remains visible without JavaScript', async ({ browser, baseURL }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 1440, height: 900 } });
  try {
    const page = await context.newPage();
    for (const pathname of ['/', '/lab']) {
      await page.goto(new URL(pathname, baseURL!).href);
      await expect(page.getByRole('link', { name: 'Draftly', exact: true }).first()).toBeVisible();
      await expect(page.locator('nav:visible').first().getByRole('link').nth(1)).toBeVisible();
    }
  } finally {
    await context.close();
  }
});
