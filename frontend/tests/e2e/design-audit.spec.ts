import { expect, test } from "@playwright/test";
import { inventoryRoutes } from "./routes";

const expectedTokens = {
  "--canvas": "#f3f5f8",
  "--surface": "#ffffff",
  "--ink": "#0f1b2e",
  "--muted-ink": "#566377",
  "--border": "#dce2ea",
  "--border-strong": "#a7b3c2",
  "--forest": "#1b3358",
  "--soft-green": "#e7eef8",
  "--teal": "#176b75",
  "--amber": "#9c5b0b",
  "--amber-text": "#784405",
  "--red": "#a43d45",
  "--selected-bg": "#eaf0f8",
  "--ring": "#176b75",
  "--navy-950": "#0b1628",
  "--gold": "#c69436",
  "--gold-strong": "#74510f",
} as const;

test("every route conforms to the Draftly visual system", async ({
  browser,
}) => {
  test.setTimeout(120_000);
  const context = await browser.newContext({
    viewport: { width: 1024, height: 768 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const problems: string[] = [];
  let activeRoute = "";
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      problems.push(`${activeRoute}: ${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) =>
    problems.push(`${activeRoute}: pageerror: ${error.message}`),
  );

  for (const route of inventoryRoutes) {
    activeRoute = route;
    await page.goto(route, { waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await expect
      .poll(() => page.evaluate(() => document.fonts.status))
      .toBe("loaded");
    const probe = await page.evaluate((tokens) => {
      const root = getComputedStyle(document.documentElement);
      const visible = (element: Element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return (
          rect.width > 0 && rect.height > 0 && style.visibility !== "hidden"
        );
      };
      const radiusViolations = [...document.querySelectorAll(".rounded")]
        .filter(visible)
        .map((element) => ({
          tag: element.tagName,
          radius: Number.parseFloat(getComputedStyle(element).borderRadius),
        }))
        .filter(({ radius }) => radius !== 6);
      const gradientViolations = [...document.querySelectorAll("body *")]
        .filter(visible)
        .filter((element) =>
          getComputedStyle(element).backgroundImage.includes("gradient"),
        ).length;
      const shadowViolations = [...document.querySelectorAll("body *")]
        .filter(visible)
        .filter((element) => {
          // Elevation comes only from the named shadow tokens (card, raised,
          // popover); anything else is an unreviewed shadow.
          const permittedElevation = ["shadow-card", "shadow-raised", "shadow-popover"].some(
            (token) =>
              element.classList.contains(token) ||
              element.classList.contains(`hover:${token}`),
          );
          return (
            getComputedStyle(element).boxShadow !== "none" &&
            !permittedElevation
          );
        }).length;
      const iconViolations = [...document.querySelectorAll("svg.lucide")]
        .filter(visible)
        .map((element) => ({
          width: element.getBoundingClientRect().width,
          height: element.getBoundingClientRect().height,
          stroke: element.getAttribute("stroke-width"),
        }))
        .filter(
          ({ width, height, stroke }) =>
            width > 24.5 || height > 24.5 || stroke !== "1.5",
        );
      const rowViolations = [...document.querySelectorAll("tr")]
        .filter(visible)
        .map((element) => ({
          height: element.getBoundingClientRect().height,
          text: element.textContent?.trim().slice(0, 80),
        }))
        .filter(({ height }) => height < 39.5 || height > 44.5);
      return {
        canvas: getComputedStyle(document.body).backgroundColor,
        overflow:
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
        letterSpacing: getComputedStyle(document.body).letterSpacing,
        bodyFont: getComputedStyle(document.body).fontFamily,
        headingFont: getComputedStyle(
          document.querySelector("h1, h2") ?? document.body,
        ).fontFamily,
        fontsLoaded: document.fonts.status,
        tokens: Object.fromEntries(
          Object.keys(tokens).map((token) => [
            token,
            root.getPropertyValue(token).trim(),
          ]),
        ),
        radiusViolations,
        gradientViolations,
        shadowViolations,
        iconViolations,
        rowViolations,
      };
    }, expectedTokens);

    expect(probe.canvas, route).toBe("rgb(243, 245, 248)");
    expect(probe.overflow, route).toBeLessThanOrEqual(0);
    expect(["0px", "normal"], route).toContain(probe.letterSpacing);
    expect(probe.bodyFont, route).toContain("IBM Plex Sans");
    expect(probe.bodyFont, route).toContain("Noto Sans Sinhala");
    // Page titles set in the display serif; section headings in Plex. Either
    // way the Sinhala counterpart of the same face follows it.
    expect(probe.headingFont, route).toMatch(/Source Serif 4[\s\S]*Noto Serif Sinhala|IBM Plex Sans[\s\S]*Noto Sans Sinhala/);
    expect(probe.tokens, route).toEqual(expectedTokens);
    expect(probe.radiusViolations, route).toEqual([]);
    expect(probe.gradientViolations, route).toBe(0);
    expect(probe.shadowViolations, route).toBe(0);
    expect(probe.iconViolations, route).toEqual([]);
    expect(probe.rowViolations, route).toEqual([]);
  }

  expect(problems).toEqual([]);
  await context.close();
});
