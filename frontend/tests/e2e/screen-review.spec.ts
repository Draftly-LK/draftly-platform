import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

// Evidence capture for the build-review loop, not a regression test: it writes
// into docs/review/, so it runs only when asked, into a folder for that date:
//   SCREEN_DATE=2026-09-18 SCREEN_SLUG=home SCREEN_PATH=/ pnpm test:e2e screen-review
const route = process.env.SCREEN_PATH ?? "/";
const slug = process.env.SCREEN_SLUG ?? "home";
const date = process.env.SCREEN_DATE ?? "";
const evidenceDir = path.resolve(process.cwd(), "..", "docs", "review", slug, date);

test.skip(
  !/^\d{4}-\d{2}-\d{2}$/.test(date),
  "set SCREEN_DATE=YYYY-MM-DD to capture review evidence",
);

for (const viewport of [{ name: "1440x900", width: 1440, height: 900 }, { name: "1024x768", width: 1024, height: 768 }]) {
  test(`${slug} ${viewport.name} review`, async ({ browser }) => {
    await mkdir(evidenceDir, { recursive: true });
    const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, reducedMotion: "reduce" });
    const page = await context.newPage();
    const consoleProblems: string[] = [];
    page.on("console", (message) => { if (["error", "warning"].includes(message.type())) consoleProblems.push(`${message.type()}: ${message.text()}`); });
    page.on("pageerror", (error) => consoleProblems.push(`pageerror: ${error.message}`));
    await page.goto(route, { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toBeVisible();
    await page.waitForTimeout(300);
    const axe = await new AxeBuilder({ page }).analyze();
    const serious = axe.violations.filter((violation) => violation.impact === "serious" || violation.impact === "critical");
    const probe = await page.evaluate(() => {
      const body = getComputedStyle(document.body);
      const heading = document.querySelector("h1");
      const rounded = document.querySelector(".rounded");
      return {
        canvas: body.backgroundColor,
        bodyFont: body.fontFamily,
        headingFont: heading ? getComputedStyle(heading).fontFamily : null,
        radius: rounded ? getComputedStyle(rounded).borderRadius : null,
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    const result = { route, viewport, consoleProblems, seriousAxeViolations: serious.map(({ id, impact, help }) => ({ id, impact, help })), probe };
    await writeFile(path.join(evidenceDir, `results-${viewport.name}.json`), JSON.stringify(result, null, 2));
    await page.screenshot({ path: path.join(evidenceDir, `baseline-${viewport.name}.png`), fullPage: true });
    expect(consoleProblems).toEqual([]);
    expect(serious).toEqual([]);
    expect(probe.canvas).toBe("rgb(244, 243, 239)");
    expect(probe.radius).toBe("6px");
    expect(probe.overflow).toBeLessThanOrEqual(0);
    expect(probe.bodyFont).not.toMatch(/Times New Roman/i);
    expect(probe.headingFont).not.toMatch(/Arial/i);
    await context.close();
  });
}
