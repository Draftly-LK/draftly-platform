import { expect, test } from "@playwright/test";

const matter = "/matters/matter-rta-001";

// One test per screen so a gap on one screen is reported on its own instead of
// hiding every screen after it. Each test gets a fresh browser context, so the
// persisted demo store always starts from the seeded fixture.
test.describe("authoritative screen regions and governed states are present", () => {
  test.describe.configure({ timeout: 90_000 });

  test("first run: only the RTA regime is selectable", async ({ page }) => {
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
  });

  test("documents: every document state, replacement history, failed-extraction recovery", async ({
    page,
  }) => {
    await page.goto(`${matter}/documents`);
    for (const state of [
      "Uploaded",
      "Extracting",
      "Ready for review",
      "Failed",
      "Replaced",
    ]) {
      await expect(
        page.getByText(state, { exact: true }).first(),
      ).toBeVisible();
    }
    await expect(page.getByText("Unsupported in M2")).toBeVisible();
    await page.getByRole("button", { name: "plan-771-synthetic.pdf" }).click();
    await page.getByText("Replacement history").click();
    await expect(
      page.getByText("plan-771-original-synthetic.pdf"),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "registry-extract-synthetic.pdf" })
      .click();
    await expect(
      page.getByRole("button", { name: "Retry extraction" }).last(),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Enter fields manually" }),
    ).toBeVisible();
  });

  test("facts: every review state and the source conflict comparison", async ({
    page,
  }) => {
    await page.goto(`${matter}/facts`);
    for (const state of [
      "Unreviewed",
      "Verified",
      "Corrected",
      "Conflict",
      "Blocked",
    ]) {
      await expect(
        page.getByText(state, { exact: true }).first(),
      ).toBeVisible();
    }
    await page.getByRole("button", { name: "Compare sources" }).click();
    await expect(
      page.getByRole("heading", { name: "Source conflict comparison" }),
    ).toBeVisible();
    await expect(page.getByText("Candidate 1")).toBeVisible();
    await expect(page.getByText("Candidate 2")).toBeVisible();
  });

  test("workflow: a blocked mandatory step needs an override reason", async ({
    page,
  }) => {
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
  });

  test("assistant: grounded answer, citation text, insufficient authority", async ({
    page,
  }) => {
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
  });

  test("drafts: generation is blocked on unready facts; versions compare and restore", async ({
    page,
  }) => {
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
  });

  test("checks: every result state, and a recorded resolution reaches activity", async ({
    page,
  }) => {
    await page.goto(`${matter}/checks`);
    for (const state of ["Pass", "Warning", "Fail", "Needs review"]) {
      await expect(
        page.getByText(state, { exact: true }).first(),
      ).toBeVisible();
    }
    await expect(
      page.getByRole("heading", { name: /Deed schedule/ }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Resolve" }).first().click();
    await page.getByLabel("Lawyer reason").fill("Synthetic resolution review");
    await page.getByRole("button", { name: "Record resolution" }).click();

    await page.goto(`${matter}/activity`);
    await expect(
      page.getByText("Check resolved", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Live session", { exact: true })).toBeVisible();
  });

  test("library surfaces: history and the authority library", async ({
    page,
  }) => {
    await page.goto("/history");
    await expect(
      page.getByText("Resume synthetic RTA transfer matter"),
    ).toBeVisible();
    await expect(
      page.getByText("Fact corrected", { exact: true }),
    ).toBeVisible();

    await page.goto("/library");
    await expect(page.getByText("Candidate — do not rely")).toBeVisible();
    await expect(
      page.getByText(/Legal text remains lawyer-owned/),
    ).toBeVisible();
  });
});
