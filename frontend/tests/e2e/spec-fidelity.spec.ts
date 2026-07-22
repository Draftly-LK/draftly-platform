import { expect, test } from "@playwright/test";

const matter = "/matters/matter-rta-001";

test("authoritative screen regions and governed states are present", async ({
  page,
}) => {
  test.setTimeout(240_000);
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());

  await page.goto("/new");
  await expect(
    page.getByRole("heading", { name: "Draftly", level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "RTA Available in M2" }),
  ).toBeEnabled();
  await expect(page.getByRole("button", { name: /RDO/ })).toBeDisabled();
  await expect(
    page.getByRole("button", { name: /Apartment Ownership/ }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: /Special Area/ }),
  ).toBeDisabled();

  await page.goto(`${matter}/documents`);
  for (const state of [
    "Uploaded",
    "Extracting",
    "Ready for review",
    "Failed",
    "Replaced",
  ]) {
    await expect(page.getByText(state, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByText("Unsupported in M2")).toBeVisible();
  await page.getByRole("button", { name: "plan-771-synthetic.pdf" }).click();
  await page.getByText("Replacement history").click();
  await expect(page.getByText("plan-771-original-synthetic.pdf")).toBeVisible();
  await page
    .getByRole("button", { name: "registry-extract-synthetic.pdf" })
    .click();
  await expect(
    page.getByRole("button", { name: "Retry extraction" }).last(),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Enter fields manually" }),
  ).toBeVisible();

  await page.goto(`${matter}/facts`);
  for (const state of [
    "Unreviewed",
    "Verified",
    "Corrected",
    "Conflict",
    "Blocked",
  ]) {
    await expect(page.getByText(state, { exact: true }).first()).toBeVisible();
  }
  await page.getByRole("button", { name: "Compare sources" }).click();
  await expect(
    page.getByRole("heading", { name: "Source conflict comparison" }),
  ).toBeVisible();
  await expect(page.getByText("Candidate 1")).toBeVisible();
  await expect(page.getByText("Candidate 2")).toBeVisible();

  await page.goto(`${matter}/workflow`);
  await page.getByRole("button", { name: /Check encumbrances/ }).click();
  const override = page.getByLabel(
    "Override reason required for blocked mandatory step",
  );
  await expect(override).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Complete step" }),
  ).toBeDisabled();
  await override.fill("Synthetic lawyer override for browser review");
  await expect(
    page.getByRole("button", { name: "Complete step" }),
  ).toBeEnabled();

  await page.goto("/assistant");
  await expect(
    page.getByRole("heading", { name: "Grounded answer" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Citation 1/ })
    .first()
    .click();
  await expect(page.getByText("Exact supporting text")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Insufficient authority" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Request authority review" }),
  ).toBeVisible();

  await page.goto(`${matter}/drafts`);
  await page.getByRole("button", { name: "New draft" }).click();
  await page.getByRole("button", { name: "Generate draft" }).click();
  await expect(page.getByText("Draft generation blocked")).toBeVisible();
  await expect(page.getByText(/Unready required facts/)).toBeVisible();

  await page.goto(`${matter}/drafts/draft-form8-001`);
  await page.getByRole("button", { name: "Compare versions" }).click();
  await expect(
    page.getByRole("heading", { name: "Previous version" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Current version" }),
  ).toBeVisible();
  await page.getByLabel("Version").selectOption("draftver-001");
  await expect(
    page.getByText("Viewing a previous version", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Restore this version" }),
  ).toBeVisible();

  await page.goto(`${matter}/checks`);
  for (const state of ["Pass", "Warning", "Fail", "Needs review"]) {
    await expect(page.getByText(state, { exact: true }).first()).toBeVisible();
  }
  await expect(
    page.getByRole("heading", { name: /Deed schedule/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Resolve" }).first().click();
  await page.getByLabel("Lawyer reason").fill("Synthetic resolution review");
  await page.getByRole("button", { name: "Record resolution" }).click();

  await page.goto(`${matter}/activity`);
  await expect(page.getByText("Check resolved", { exact: true })).toBeVisible();
  await expect(page.getByText("Live session", { exact: true })).toBeVisible();

  await page.goto("/workflows");
  await page.getByRole("tab", { name: "Draft templates" }).click();
  await expect(page.getByText("Form 8 transfer template")).toBeVisible();
  await page.getByRole("tab", { name: "Question sets" }).click();
  await expect(page.getByText("RTA examination question set")).toBeVisible();
  await page.getByRole("tab", { name: "Worked examples" }).click();
  await expect(
    page.getByText("Synthetic transfer examination example"),
  ).toBeVisible();

  await page.goto("/history");
  await expect(
    page.getByText("Resume synthetic RTA transfer matter"),
  ).toBeVisible();
  await expect(page.getByText("Fact corrected", { exact: true })).toBeVisible();

  await page.goto("/library");
  await expect(page.getByText("Candidate — do not rely")).toBeVisible();
  await expect(page.getByText(/Legal text remains lawyer-owned/)).toBeVisible();
});
