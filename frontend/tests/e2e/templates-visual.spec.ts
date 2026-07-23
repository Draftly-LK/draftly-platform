import { expect, test } from "@playwright/test";
import { listTemplates } from "@/lib/templates";
import { templatePdfPages } from "@/lib/templates/pdf-pages";

test.describe("template PDF visual compare", () => {
  test("every form has PDF pages and a working compare route", async ({
    page,
  }) => {
    const templates = listTemplates();
    expect(templates.length).toBe(20);

    for (const { meta } of templates) {
      const pages = templatePdfPages[meta.id] ?? [];
      expect(pages.length, meta.id).toBeGreaterThan(0);

      const response = await page.goto(`/dev/templates/${meta.id}/compare`);
      expect(response?.ok(), meta.id).toBeTruthy();
      await expect(
        page.getByText("Gazette PDF").or(page.getByText("ගැසට් PDF")),
      ).toBeVisible();

      for (const pageNo of pages) {
        const name = `page-${String(pageNo).padStart(2, "0")}.png`;
        const img = page.locator(`img[src="/api/dev/form-pages/${name}"]`);
        await expect(img, `${meta.id} ${name}`).toBeVisible();
      }

      await expect(page.locator(".template-a4-sheet")).toBeVisible();
      await expect(page.locator(".ProseMirror")).toBeVisible({
        timeout: 15_000,
      });
    }
  });

  test("Form 08 compare shows PDF pages and matching office box", async ({
    page,
  }) => {
    await page.goto("/dev/templates/form-08-instrument-of-transfer/compare");
    await expect(
      page.locator('img[src="/api/dev/form-pages/page-04.png"]'),
    ).toBeVisible();
    await expect(
      page.locator('img[src="/api/dev/form-pages/page-05.png"]'),
    ).toBeVisible();
    await expect(page.locator(".ProseMirror")).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(".office-use-box")).toBeVisible();
    await expect(page.locator(".ProseMirror h1")).toContainText("පැවරීමේ");
  });
});
