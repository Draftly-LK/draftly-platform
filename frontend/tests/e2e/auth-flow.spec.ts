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

  // /onboarding is guarded twice: the page component itself redirects to "/"
  // when Clerk or the API is not configured, and Clerk's middleware protects
  // the route (it is not in the public-route matcher) for signed-out users.
  // In this environment Clerk and the API are both configured, so the
  // middleware runs first and wins — an unauthenticated visitor never
  // reaches the page component and is bounced to /sign-in, same as /profile.
  test("protected route /onboarding redirects unauthenticated user to /sign-in", async ({
    page,
  }) => {
    await page.goto("/onboarding");
    await expect(page).toHaveURL(/\/sign-in/);
  });

  test("sign-in page renders title and email/password copy", async ({ page }) => {
    await page.goto("/sign-in");
    await expect(
      page.getByRole("heading", { name: "Sign in to Draftly" }),
    ).toBeVisible();
    await expect(
      page.getByText("Continue with a connected account, or sign in with your email and password."),
    ).toBeVisible();
  });

  test("sign-up page renders title and email/password copy", async ({ page }) => {
    await page.goto("/sign-up");
    await expect(
      page.getByRole("heading", { name: "Create your Draftly account" }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "Continue with a connected account, or register with your email address and password.",
      ),
    ).toBeVisible();
  });
});
