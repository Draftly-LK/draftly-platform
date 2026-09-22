import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { inventoryRoutes } from "./routes";

test("all routes have no serious or critical accessibility violations", async ({
  browser,
}) => {
  test.setTimeout(180_000);
  const context = await browser.newContext({
    viewport: { width: 1024, height: 768 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const failures: Array<{
    route: string;
    id: string;
    impact: string | null | undefined;
  }> = [];

  for (const route of inventoryRoutes) {
    await page.goto(route, { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toBeVisible();
    const result = await new AxeBuilder({ page }).analyze();
    failures.push(
      ...result.violations
        .filter(({ impact }) => impact === "serious" || impact === "critical")
        .map(({ id, impact }) => ({ route, id, impact })),
    );
    const statusProblems = await page
      .locator("[data-status]")
      .evaluateAll(
        (items) =>
          items
            .filter((item) => item.querySelector("svg"))
            .filter((item) => !item.textContent?.trim()).length,
      );
    expect(statusProblems, route).toBe(0);
  }

  expect(failures).toEqual([]);
  await context.close();
});

test("command palette: keyboard open, Escape, focus return, and visible focus ring", async ({
  page,
}) => {
  test.setTimeout(90_000);
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const searchButton = page.getByRole("button", { name: /Search workspace/ });
  await expect(searchButton).toBeVisible();
  expect(pageErrors).toEqual([]);
  await searchButton.click();
  await page.waitForTimeout(100);
  expect({ pageErrors, consoleErrors }).toEqual({
    pageErrors: [],
    consoleErrors: [],
  });
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.keyboard.down("Control");
  await page.keyboard.press("k");
  await page.keyboard.up("Control");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await expect(searchButton).toBeFocused();
  // Auto-retrying on purpose. Under reduced motion globals.css forces
  // `transition-duration: 0.01ms` on everything, so the ring is mid-transition
  // (computed 0px) for the first frame after focus returns; a one-shot
  // getComputedStyle read raced that frame. The ring itself is asserted in
  // full: 2px solid in the `ring` token, offset 2px (docs/plan.md).
  await expect(searchButton).toHaveCSS("outline-width", "2px");
  await expect(searchButton).toHaveCSS("outline-style", "solid");
  await expect(searchButton).toHaveCSS("outline-color", "rgb(38, 116, 122)");
  await expect(searchButton).toHaveCSS("outline-offset", "2px");
  expect({ pageErrors, consoleErrors }).toEqual({
    pageErrors: [],
    consoleErrors: [],
  });
});

test("fact correction dialog is keyboard reachable, focuses its field, and closes on Escape", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/matters/matter-rta-001/facts");
  await tabTo(page, "Correct");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByLabel("Corrected value")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("reduced motion is honoured and the workspace reflows at 200 percent", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await page.emulateMedia({ reducedMotion: "reduce" });
  // /new carries the only entrance animation in the app (the first-run fade).
  for (const route of ["/matters/matter-rta-001/facts", "/new"]) {
    await page.goto(route);
    await expect(page.locator("main h1").last()).toBeVisible();
    const motionViolation = await page.evaluate(() =>
      [...document.querySelectorAll("body *")].some((element) => {
        const style = getComputedStyle(element);
        const durations = style.animationDuration
          .split(",")
          .map((value) => Number.parseFloat(value) || 0);
        return durations.some((duration) => duration > 0.011);
      }),
    );
    expect(motionViolation, route).toBe(false);
  }

  await page.setViewportSize({ width: 512, height: 768 });
  for (const route of [
    "/matters/matter-rta-001/facts",
    "/matters/matter-rta-001/drafts/draft-form8-001",
    "/assistant",
  ]) {
    await page.goto(route);
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow, route).toBeLessThanOrEqual(0);
  }
});

async function tabTo(page: Page, name: string) {
  for (let index = 0; index < 100; index += 1) {
    const activeName = await page.evaluate(() => {
      const active = document.activeElement;
      if (!(active instanceof HTMLElement)) return "";
      if (!active.matches("a, button, input, select, textarea, [tabindex]")) {
        return "";
      }
      return `${active.getAttribute("aria-label") ?? ""} ${active.textContent ?? ""}`.trim();
    });
    if (activeName.includes(name)) return;
    await page.keyboard.press("Tab");
  }
  throw new Error(`Keyboard focus did not reach ${name}`);
}
