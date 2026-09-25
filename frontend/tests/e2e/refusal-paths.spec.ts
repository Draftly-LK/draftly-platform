import { expect, test } from "@playwright/test";

// Appendix A's refusals, where the offline demo can show them. The approval
// and export refusals live on API-bound screens, which need Clerk test keys
// to render (TESTING_PLAN.md §7.2); the server-side refusals are covered in
// backend/tests/db/test_lawyer_workflow.py.

const WORKFLOW = "/matters/matter-rta-001/workflow";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.goto(WORKFLOW);
});

test("a blocked mandatory step cannot be completed without a reason", async ({ page }) => {
  await page.getByRole("button", { name: /Check encumbrances/ }).click();

  const complete = page.getByRole("button", { name: "Complete step" });
  const reason = page.getByLabel("Override reason required for blocked mandatory step");
  await expect(reason).toBeVisible();
  await expect(complete).toBeDisabled();

  // Whitespace is not a reason.
  await reason.fill("   ");
  await expect(complete).toBeDisabled();

  await reason.fill("Synthetic reason: extract re-requested from the registry");
  await expect(complete).toBeEnabled();
  await complete.click();

  await expect(page.getByText("Override reason recorded in the audit trail.")).toBeVisible();
});

test("the override is recorded as an override in the activity", async ({ page }) => {
  await page.getByRole("button", { name: /Check encumbrances/ }).click();
  await page
    .getByLabel("Override reason required for blocked mandatory step")
    .fill("Synthetic reason");
  await page.getByRole("button", { name: "Complete step" }).click();

  await page.goto("/matters/matter-rta-001/activity");

  await expect(page.getByRole("listitem").first()).toContainText("Workflow step overridden");
});

test("a step that is not blocked asks for no override", async ({ page }) => {
  await page.getByRole("button", { name: /Examine title and parcel/ }).click();

  await expect(
    page.getByLabel("Override reason required for blocked mandatory step"),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Complete step" })).toBeEnabled();
});
