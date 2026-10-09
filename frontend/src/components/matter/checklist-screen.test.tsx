// @vitest-environment happy-dom
import { screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import type { WorkChecklistRead } from "@/types/work-checklist";
import { ChecklistScreen } from "./checklist-screen";

const mocks = vi.hoisted(() => ({ api: true, reads: [] as string[] }));
vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("@/lib/api/client", async (original) => ({
  ...(await original<Record<string, unknown>>()),
  isApiEnabled: () => mocks.api,
}));
vi.mock("@/lib/api/use-token-provider", () => {
  const token = async () => "synthetic";
  return { useTokenProvider: () => token };
});
vi.mock("@/lib/api/auth", () => ({ getMe: async () => ({ id: "synthetic" }) }));
vi.mock("@/lib/api/work-checklist", () => ({
  getWorkChecklist: async (
    _token: unknown,
    matterId: string,
  ): Promise<WorkChecklistRead> => {
    mocks.reads.push(matterId);
    return {
      matterId,
      tasks: [
        {
          id: "synthetic-review",
          version: 1,
          group: "documents",
          origin: "governed",
          state: "not-started",
          title: "Review synthetic facts",
          titleKey: null,
          reason: "Confirm the extracted parcel.",
          reasonKey: null,
          completedBy: null,
          completedAt: null,
          assignedTo: null,
          evidence: [],
          action: { kind: "navigate", section: "facts", targetId: null },
        },
      ],
      suggestions: [],
      progress: { total: 1, completed: 0, percent: 0, assessing: true },
      nextTaskId: "synthetic-review",
    };
  },
}));

beforeEach(() => {
  mocks.api = true;
  mocks.reads = [];
});

it("loads the current matter's real checklist controls and action targets", async () => {
  renderWithIntl(<ChecklistScreen matterId="synthetic-one" />);
  expect(await screen.findByRole("progressbar")).toHaveProperty("value", 0);
  expect(mocks.reads).toEqual(["synthetic-one"]);
  expect(screen.getByRole("heading", { name: "Checklist" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Add task" })).toBeTruthy();
  expect(
    screen.getAllByRole("link", { name: "Review" })[0]?.getAttribute("href"),
  ).toBe("/matters/synthetic-one/facts");
});

it("renders the dedicated checklist screen in Sinhala", async () => {
  renderWithIntl(<ChecklistScreen matterId="synthetic-one" />, "si");
  await screen.findByRole("progressbar");
  expect(screen.getByRole("heading", { name: "කාර්ය ලැයිස්තුව" })).toBeTruthy();
  expect(screen.queryByRole("heading", { name: "Checklist" })).toBeNull();
});

it("explains offline availability without requesting a live checklist", () => {
  mocks.api = false;
  renderWithIntl(<ChecklistScreen matterId="synthetic-one" />);
  expect(
    screen.getByText("The matter checklist needs a server connection."),
  ).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Add task" })).toBeNull();
  expect(mocks.reads).toEqual([]);
});
