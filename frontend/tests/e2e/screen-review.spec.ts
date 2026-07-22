import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const route = process.env.SCREEN_PATH ?? "/";
const slug = process.env.SCREEN_SLUG ?? "home";
const evidenceDir = path.resolve(process.cwd(), "..", "docs", "review", slug, "2026-07-22");

for (const viewport of [{ name: "1440x900", width: 1440, height: 900 }, { name: "1024x768", width: 1024, height: 768 }]) {
  test(`${slug} ${viewport.name} review`, async ({ browser }) => {
    await mkdir(evidenceDir, { recursive: true });
    const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, reducedMotion: "reduce" });
    const page = await context.newPage();
    const consoleProblems: string[] = [];
    page.on("console", (message) => { if (["error", "warning"].includes(message.type())) consoleProblems.push(`${message.type()}: ${message.text()}`); });
    page.on("pageerror", (error) => consoleProblems.push(`pageerror: ${error.message}`));
    await page.goto(route, { waitUntil: "networkidle" });
    await expect(page.locator("body")).toBeVisible();
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

