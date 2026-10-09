// @vitest-environment happy-dom
import { screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import { MatterDashboard } from "./matter-dashboard";

vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
// The assistant's network behavior is separate from this checklist regression.
vi.mock("./matter-conversation", () => ({
  MatterConversation: () => null,
}));
vi.mock("@/lib/api/client", async (original) => ({
  ...(await original<Record<string, unknown>>()),
  isApiEnabled: () => true,
}));
vi.mock("@/lib/api/use-token-provider", () => {
  const token = async () => "synthetic";
  return { useTokenProvider: () => token };
});
vi.mock("@/lib/api/auth", () => ({ getMe: async () => ({ id: "synthetic" }) }));
vi.mock("@/lib/api/work-checklist", () => ({
  getWorkChecklist: async () => new Promise(() => {}),
}));

it("keeps the checklist out of Overview", () => {
  renderWithIntl(<MatterDashboard matterId="synthetic" />);
  expect(
    screen.queryByRole("heading", { name: "Matter checklist" }),
  ).toBeNull();
  expect(screen.getByRole("heading", { name: "Overview" })).toBeTruthy();
});
