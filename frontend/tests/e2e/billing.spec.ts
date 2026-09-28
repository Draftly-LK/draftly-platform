import { expect, test } from "@playwright/test";

test("billing presents proposed single-user plans without implying enforcement", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/billing");

  await expect(
    page.getByRole("heading", { name: "Billing and plans" }),
  ).toBeVisible();
  await expect(page.getByText("Illustrative post-pilot plans")).toBeVisible();
  await expect(page.getByText("Recommended")).toBeVisible();
  await expect(
    page.getByText(
      "You will not be charged automatically when your pilot ends.",
    ),
  ).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(3);
  await expect(page.getByRole("link", { name: "Contact us" })).toHaveAttribute(
    "href",
    "/help",
  );

  const cardTops = await page
    .getByRole("article")
    .evaluateAll((cards) =>
      cards.map((card) => Math.round(card.getBoundingClientRect().top)),
    );
  expect(new Set(cardTops).size).toBe(1);

  const copy = await page.locator("main").innerText();
  expect(copy).not.toMatch(
    /\b(?:organisation|organization|firm|team seats|workspace administrator)\b/i,
  );
});

test("billing plan cards stack without horizontal overflow on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 767, height: 1000 });
  await page.goto("/billing");

  const cards = page.getByRole("article");
  await expect(cards).toHaveCount(3);
  const cardTops = await cards.evaluateAll((items) =>
    items.map((item) => Math.round(item.getBoundingClientRect().top)),
  );
  expect(new Set(cardTops).size).toBe(3);
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    ),
  ).toBeLessThanOrEqual(0);
});
