import { expect, test, type Page } from "@playwright/test";
import { inventoryRoutes } from "./routes";

test("every route holds at 1024 without page overflow", async ({ browser }) => {
  test.setTimeout(180_000);
  const context = await browser.newContext({
    viewport: { width: 1024, height: 768 },
  });
  const page = await context.newPage();
  const problems = observeProblems(page);

  for (const route of inventoryRoutes) {
    await page.goto(route, { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toBeVisible();
    expect(await horizontalOverflow(page), route).toBeLessThanOrEqual(0);
    const rail = page.locator("aside[data-app-chrome]");
    if (await rail.count()) {
      await expect(rail).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");
    } else {
      expect(route).toBe("/new");
    }
  }

  expect(problems).toEqual([]);
  await context.close();
});

test("rails collapse below 768 and representative screens reflow", async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 767, height: 900 },
  });
  const page = await context.newPage();
  const problems = observeProblems(page);

  for (const route of [
    "/",
    "/new",
    "/matters",
    "/matters/matter-rta-001/documents",
    "/matters/matter-rta-001/facts",
    "/matters/matter-rta-001/drafts/draft-form8-001",
    "/assistant",
  ]) {
    await page.goto(route, { waitUntil: "domcontentloaded" });
    const rail = page.locator("aside[data-app-chrome]");
    if (await rail.count()) {
      await expect(
        page.getByRole("button", { name: "Open navigation" }),
      ).toBeVisible();
      const railOffset = await rail.evaluate(
        (element) => new DOMMatrix(getComputedStyle(element).transform).m41,
      );
      expect(railOffset, route).toBeLessThan(0);
    } else {
      expect(route).toBe("/new");
    }
    expect(await horizontalOverflow(page), route).toBeLessThanOrEqual(0);
  }

  expect(problems).toEqual([]);
  await context.close();
});

// Skipped while the language switcher is hidden; re-enable with LocaleToggle.
test.skip("English and Sinhala locale scaffolds hold across the demo path", async ({
  page,
}) => {
  test.setTimeout(90_000);
  const problems = observeProblems(page);
  await page.goto("/");
  const toggle = page.locator("[data-locale]").first();
  await expect(toggle.getByRole("button", { name: "සිං" })).toBeVisible();
  await toggle.getByRole("button", { name: "සිං" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "si");

  for (const route of [
    "/new",
    "/matters/matter-rta-001/documents",
    "/matters/matter-rta-001/facts",
    "/matters/matter-rta-001/workflow",
    "/matters/matter-rta-001/checks",
    "/assistant",
    "/matters/matter-rta-001/drafts",
    "/matters/matter-rta-001/drafts/draft-form8-001",
    "/matters/matter-rta-001/activity",
  ]) {
    await page.goto(route, { waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("lang", "si");
    const probe = await page.evaluate(() => {
      const localeControl =
        document.querySelector<HTMLElement>("[data-locale]");
      const sinhalaButton = [
        ...(localeControl?.querySelectorAll("button") ?? []),
      ].find((button) => button.textContent?.includes("සිං"));
      return {
        bodyFont: getComputedStyle(document.body).fontFamily,
        headingFont: getComputedStyle(
          document.querySelector("h1, h2") ?? document.body,
        ).fontFamily,
        glyphFits: sinhalaButton
          ? sinhalaButton.scrollHeight <= sinhalaButton.clientHeight
          : false,
        overflow:
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
        rawKey:
          /\b(?:app|shell|home|matter|documents|facts|workflow|checks|assistant|drafts|activity)\.[a-z][\w.]*/i.test(
            document.body.innerText,
          ),
      };
    });
    expect(probe.bodyFont, route).toContain("Noto Sans Sinhala");
    expect(probe.headingFont, route).toContain("Noto Sans Sinhala");
    expect(probe.glyphFits, route).toBe(true);
    expect(probe.overflow, route).toBeLessThanOrEqual(0);
    expect(probe.rawKey, route).toBe(false);
  }

  await page.goto("/", { waitUntil: "load" });
  const currentToggle = page.locator("[data-locale]").first();
  await currentToggle.getByRole("button", { name: "EN" }).click();
  const localeCookie = (await page.context().cookies()).find(
    (cookie) => cookie.name === "draftly-locale",
  );
  expect(localeCookie?.value).toBe("en");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  expect(problems).toEqual([]);
});

test("representative workspace holds with 30 percent longer labels", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  for (const route of [
    "/matters",
    "/assistant",
    "/matters/matter-rta-001/checks",
  ]) {
    await page.goto(route, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => {
      for (const element of document.querySelectorAll<HTMLElement>(
        "main h1, main h2, main h3, main button, main a, main label",
      )) {
        if (element.children.length > 0) continue;
        const value = element.textContent?.trim();
        if (!value || value.length < 4) continue;
        element.textContent = `${value} ${value.slice(0, Math.ceil(value.length * 0.3))}`;
      }
    });
    expect(await horizontalOverflow(page), route).toBeLessThanOrEqual(0);
  }
});

function observeProblems(page: Page) {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      problems.push(`${page.url()} ${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) =>
    problems.push(`${page.url()} pageerror: ${error.message}`),
  );
  return problems;
}

async function horizontalOverflow(page: Page) {
  return page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
}
