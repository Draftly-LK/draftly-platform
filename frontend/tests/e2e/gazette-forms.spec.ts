import { expect, test, type Page } from "@playwright/test";

// The gazette drafting workspace on the synthetic demo forms: prescribed
// wording cannot change, both drafting modes share one set of values, and the
// field-decision rules match the API's.

const FORM_08 = "/matters/matter-rta-001/drafts/demo-form-08";
const FORM_12 = "/matters/matter-rta-001/drafts/demo-form-12";

async function open(page: Page, path: string) {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.goto(path);
  await expect(page.locator(".gz-page")).toBeVisible();
}

const blank = (page: Page, id: string) => page.locator(`[data-gz-slot="${id}"]`).locator("input, textarea, button");

test("the prescribed wording cannot be typed over, deleted, or pasted into", async ({ page }) => {
  await open(page, FORM_08);
  const pageText = page.locator(".gz-page");
  const title = pageText.locator(".gz-title");
  const before = await pageText.innerText();

  await title.click({ clickCount: 3 });
  await page.keyboard.type("altered");
  await page.keyboard.press("Backspace");
  await page.keyboard.press("Delete");
  await page.keyboard.insertText("pasted");
  await page.keyboard.press("Control+a");
  await page.keyboard.press("Backspace");

  await expect(title).toHaveText("පැවරීමේ හෝ විකිණීමේ සාධන පත්‍රය");
  expect(await pageText.innerText()).toBe(before);
  await expect(pageText).toHaveAttribute("contenteditable", "false");
});

test("a blank filled on the page is the same blank field by field, and it persists", async ({ page }) => {
  await open(page, FORM_08);
  await page.getByRole("button", { name: "Fill in document" }).click();

  const conditions = blank(page, "f08.7");
  await conditions.fill("Synthetic condition text");
  await expect(page.getByText(/blanks filled/)).toContainText("18 of 44");

  // The page's blank is now the active step in field-by-field review.
  await page.getByRole("button", { name: "Field by field" }).click();
  await expect(page.locator('[data-slot-card="f08.7"]').locator("textarea")).toHaveValue("Synthetic condition text");

  // Editing it in the panel updates the page.
  await page.locator('[data-slot-card="f08.7"]').locator("textarea").fill("Revised synthetic condition");
  await expect(conditions).toHaveValue("Revised synthetic condition");

  await page.reload();
  await expect(page.locator(".gz-page")).toBeVisible();
  await expect(blank(page, "f08.7")).toHaveValue("Revised synthetic condition");
});

test("field by field walks every blank in printed order, then the fields the page has no blank for", async ({ page }) => {
  await open(page, FORM_08);
  await expect(page.getByText("Blank 1 of 47")).toBeVisible();
  await expect(page.locator('[data-field-card="district"]')).toBeVisible();

  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.getByText("Blank 2 of 47")).toBeVisible();
  await expect(page.locator('[data-field-card="ds_division"]')).toBeVisible();

  await page.getByRole("button", { name: "Next empty blank" }).click();
  await expect(page.locator('[data-gz-slot="f08.1.aee"] button')).toHaveAttribute("aria-pressed", "true");
});

test("a critical field is confirmed or cleared, never typed, and clearing needs a reason", async ({ page }) => {
  await open(page, FORM_08);
  await page.getByRole("button", { name: "Fill in document" }).click();
  await blank(page, "f08.1.a").click();

  const card = page.locator('[data-field-card="district"]');
  await expect(card.getByText("Critical", { exact: true })).toBeVisible();
  await expect(card.getByRole("button", { name: "Correct" })).toHaveCount(0);

  await card.getByRole("button", { name: "Clear" }).click();
  const clearField = card.getByRole("button", { name: "Clear field" });
  await expect(clearField).toBeDisabled();
  await card.getByLabel("Reason (required)").fill("   ");
  await expect(clearField).toBeDisabled();
  await card.getByLabel("Reason (required)").fill("Synthetic reason: wrong parcel");
  await clearField.click();

  await expect(blank(page, "f08.1.a")).toHaveAttribute("data-status", "unresolved");
  await expect(card.getByText("Unresolved").first()).toBeVisible();
});

test("the one lawyer-authored field on Form 12 has no blank, and is corrected from the side list", async ({ page }) => {
  await open(page, FORM_12);
  await page.getByRole("button", { name: "Fill in document" }).click();
  await page.getByRole("button", { name: /Cancellation particulars/ }).click();

  const card = page.locator('[data-field-card="cancellation_particulars"]');
  await card.getByRole("button", { name: "Correct" }).click();
  await card.getByLabel("Corrected text").fill("Synthetic cancellation particulars");
  await card.getByLabel("Reason (required)").fill("Synthetic reason");
  await card.getByRole("button", { name: "Save correction" }).click();

  await expect(card.getByText("Synthetic cancellation particulars")).toBeVisible();
});
