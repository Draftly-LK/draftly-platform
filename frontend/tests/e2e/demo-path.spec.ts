import { expect, test } from "@playwright/test";

test("complete synthetic lawyer-in-the-loop demo path", async ({ page }) => {
  test.setTimeout(180_000);
  const problems: string[] = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      problems.push(`${page.url()} ${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) =>
    problems.push(`${page.url()} ${error.message}`),
  );

  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.goto("/new");
  await page.getByRole("button", { name: "Continue with RTA" }).click();
  await page.getByRole("button", { name: "Continue with RTA" }).click();
  await page.getByLabel("Matter reference").fill("RTA-2026-SYN-015");
  await page.getByLabel("Optional client reference").fill("CLIENT-SYN-105");
  await page.getByRole("button", { name: "Continue with RTA" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "deed-9001-synthetic.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("Synthetic browser fixture"),
  });
  await page.getByRole("button", { name: "Create matter" }).click();
  await expect(page).toHaveURL(/\/matters\/matter-rta-002$/);
  await expect(
    page.getByRole("heading", { name: "RTA-2026-SYN-015" }),
  ).toBeVisible();

  const matter = "/matters/matter-rta-002";
  await page.getByRole("link", { name: "Documents", exact: true }).click();
  await expect(page).toHaveURL(`${matter}/documents`);
  await expect(page.getByText("deed-9001-synthetic.pdf")).toBeVisible();
  await expect(page.getByText("Ready for review", { exact: true })).toBeVisible(
    {
      timeout: 5_000,
    },
  );

  await page.goto(`${matter}/facts`);
  await page.getByRole("button", { name: "Verify", exact: true }).click();
  await page.getByRole("button", { name: "Compare sources" }).click();
  await page.getByRole("button", { name: "Use this value" }).first().click();
  await expect(
    page.getByText("Corrected", { exact: true }).last(),
  ).toBeVisible();

  await page.goto(`${matter}/workflow`);
  await page.getByRole("button", { name: "Complete step" }).click();
  await expect(
    page.getByText("Workflow step completed and added to activity."),
  ).toBeVisible();

  await page.goto(`${matter}/checks`);
  await page.getByRole("button", { name: "Resolve" }).first().click();
  await page
    .getByLabel("Lawyer reason")
    .fill("Synthetic end-to-end resolution");
  await page.getByRole("button", { name: "Record resolution" }).click();

  await page.goto("/assistant");
  await page
    .getByLabel("Ask a legal research question")
    .fill("What synthetic facts need review?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await page.getByRole("button", { name: "Add to matter" }).first().click();

  await page.goto(`${matter}/drafts`);
  await page.getByRole("button", { name: "New draft" }).click();
  await page.getByRole("button", { name: "Generate draft" }).click();
  await expect(page).toHaveURL(/\/drafts\/draft-live-002$/);
  await expect(page.locator("[data-fact-chip]").first()).toBeVisible();
  await page.getByRole("button", { name: "Save new version" }).click();
  await page.getByRole("button", { name: "Compare versions" }).click();
  await expect(
    page.getByRole("heading", { name: "Previous version" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close comparison" }).click();
  await page.getByRole("button", { name: "Approve draft" }).click();
  await page.getByRole("button", { name: "Export PDF" }).click();

  await page.goto(`${matter}/activity`);
  for (const event of [
    "Matter created",
    "Document uploaded",
    "Document ready for review",
    "Fact verified",
    "Fact corrected",
    "Workflow step completed",
    "Check resolved",
    "Assistant question asked",
    "Assistant answer added to matter",
    "Draft created",
    "Draft version created",
    "Draft approved",
    "Draft exported as PDF",
  ]) {
    await expect(page.getByText(event, { exact: true })).toBeVisible();
  }

  expect(problems).toEqual([]);
});
