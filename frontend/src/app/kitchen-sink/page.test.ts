import { afterEach, describe, expect, it, vi } from "vitest";

const notFound = vi.fn(() => {
  throw new Error("NEXT_NOT_FOUND");
});
vi.mock("next/navigation", () => ({ notFound }));
vi.mock("next-intl/server", () => ({ getTranslations: async () => (key: string) => key }));
// The page body is irrelevant here; only the production guard is under test.
vi.mock("@/components/shell/app-shell", () => ({ AppShell: () => null }));
vi.mock("@/components/shell/page-header", () => ({ PageHeader: () => null }));

// The page pulls in most of the UI kit; under the parallel coverage run its first
// import can take longer than the default 5s.
const SLOW_IMPORT_MS = 30_000;

afterEach(() => {
  vi.resetModules();
  vi.unstubAllEnvs();
  notFound.mockClear();
});

describe("kitchen-sink page", () => {
  // Development first: react/jsx-dev-runtime is cached by the first import, and under
  // NODE_ENV=production it has no jsxDEV, so the order matters.
  it("renders in development", async () => {
    vi.stubEnv("NODE_ENV", "development");
    const { default: KitchenSinkPage } = await import("./page");

    await expect(KitchenSinkPage()).resolves.toBeTruthy();
    expect(notFound).not.toHaveBeenCalled();
  }, SLOW_IMPORT_MS);

  it("answers 404 in a production build", async () => {
    vi.stubEnv("NODE_ENV", "production");
    const { default: KitchenSinkPage } = await import("./page");

    await expect(KitchenSinkPage()).rejects.toThrow("NEXT_NOT_FOUND");
    expect(notFound).toHaveBeenCalledOnce();
  }, SLOW_IMPORT_MS);
});
