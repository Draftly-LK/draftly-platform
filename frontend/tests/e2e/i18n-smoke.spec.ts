import { expect, test } from "@playwright/test";

test("Sinhala scaffold covers the demo path without raw keys or clipping", async ({
  page,
}) => {
  test.setTimeout(60_000);
  const problems: string[] = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      problems.push(`${page.url()} ${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) =>
    problems.push(`${page.url()} pageerror: ${error.message}`),
  );

  await page.goto("/");
  await page.getByRole("button", { name: "සිං" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "si");

  for (const route of [
    "/",
    "/matters/matter-rta-001/facts",
    "/assistant",
    "/matters/matter-rta-001/drafts/draft-form8-001",
  ]) {
    await page.goto(route);
    await expect(page.locator("body")).toBeVisible();
    const localeToggle = page.locator("[data-locale]").first();
    if (await localeToggle.count()) {
      await expect(localeToggle).toHaveAttribute("data-locale", "si");
    }
    const probe = await page.evaluate(() => ({
      overflow:
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
      bodyFont: getComputedStyle(document.body).fontFamily,
      headingFont: getComputedStyle(
        document.querySelector("h1, h2") ?? document.body,
      ).fontFamily,
      lineHeight: Number.parseFloat(getComputedStyle(document.body).lineHeight),
      text: document.body.innerText,
    }));
    expect(probe.overflow).toBeLessThanOrEqual(0);
    expect(probe.bodyFont).toContain("Noto Sans Sinhala");
    expect(probe.headingFont).toContain("Noto Serif Sinhala");
    expect(probe.lineHeight).toBeGreaterThanOrEqual(24);
    expect(probe.text).not.toMatch(/\b(?:app|shell|facts|assistant|draft)\.[a-z]/i);
  }

  expect(problems).toEqual([]);
});
