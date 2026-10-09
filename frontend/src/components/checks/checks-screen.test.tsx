// @vitest-environment happy-dom
import { screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import en from "@/lib/i18n/messages/en.json";
import { ChecksScreen } from "./checks-screen";
import type * as ApiClient from "@/lib/api/client";
const state = vi.hoisted(() => ({ fail: false }));
beforeEach(() => {
  state.fail = false;
});
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof ApiClient>()),
  isApiEnabled: () => true,
}));
vi.mock("@/lib/api/use-token-provider", () => ({
  useTokenProvider: () => token,
}));
vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));
vi.mock("@/components/matter/requirements-panel", () => ({
  RequirementsPanel: () => null,
}));
vi.mock("./check-scope-selector", () => ({ CheckScopeSelector: () => null }));
vi.mock("@/lib/api/checks", () => ({
  listCompleteIssues: async () => {
    if (state.fail) throw new Error("synthetic unavailable");
    return {
      items: [],
      gates: {
        blocksDraftGeneration: false,
        blocksApproval: false,
        blocksRegistrationReadyExport: false,
        openStatutoryBlockerIds: [],
        openBlockingIssueIds: [],
        staleCheckIds: ["synthetic-check"],
      },
    };
  },
  listCheckResults: async () => ({
    items: [
      {
        id: "synthetic-check",
        outcome: "PASS",
        explanationKey: "checks.checkResults",
        provisional: false,
      },
    ],
    page: { nextCursor: null },
  }),
}));
const token = async () => "synthetic-token";
it("labels historical passes as stale and explains that unblocked issue gates do not establish readiness", async () => {
  renderWithIntl(<ChecksScreen matterId="synthetic-matter" />);
  expect(
    await screen.findByText("Needs review - recorded result is stale"),
  ).toBeTruthy();
  expect(screen.getByText("Recorded outcome: Passed")).toBeTruthy();
  expect(screen.getAllByText("No recorded blocking issues")).toHaveLength(3);
  expect(
    screen.getByText(/Issue gates do not establish overall readiness/),
  ).toBeTruthy();
});
it("does not claim no issues when the issue request failed", async () => {
  state.fail = true;
  renderWithIntl(<ChecksScreen matterId="synthetic-failed-matter" />);
  await screen.findByText(en.checks.loadError);
  expect(screen.queryByText("No issues found.")).toBeNull();
  expect(screen.queryByText("Not run")).toBeNull();
});
