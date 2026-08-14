import { expect, test } from "@playwright/test";

test.describe("Auth and Security Gating E2E Tests", () => {
  test("clerk-not-configured error page renders cleanly", async ({ page }) => {
    await page.goto("/clerk-not-configured");
    await expect(
      page.getByRole("heading", { name: "Draftly is not configured" }),
    ).toBeVisible();
    await expect(
      page.getByText("The authentication provider (Clerk) is not set up"),
    ).toBeVisible();
  });

  test("protected route /profile redirects unauthenticated user to /sign-in", async ({ page }) => {
    await page.goto("/profile");
    await expect(page).toHaveURL(/\/sign-in/);
  });

  test("sign-in page renders title and email/password copy", async ({ page }) => {
    await page.goto("/sign-in");
    await expect(
      page.getByRole("heading", { name: "Sign in to Draftly" }),
    ).toBeVisible();
    await expect(
      page.getByText("Continue with Google or sign in with your email and password."),
    ).toBeVisible();
  });

  test("sign-up page renders title and email/password copy", async ({ page }) => {
    await page.goto("/sign-up");
    await expect(
      page.getByRole("heading", { name: "Create your Draftly account" }),
    ).toBeVisible();
    await expect(
      page.getByText("Sign up with Google, or register with your email address and password."),
    ).toBeVisible();
  });
});
