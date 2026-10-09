// @vitest-environment happy-dom
import { webcrypto } from "node:crypto";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import { RequirementsPanel } from "./requirements-panel";
import { ApiError } from "@/lib/api/client";

const mocks = vi.hoisted(() => ({
  calls: [] as unknown[][],
  fail: false,
  inboxFail: false,
  assessmentPending: false,
}));
vi.mock("@/lib/api/auth", () => ({
  getMe: async () => ({ id: "synthetic-actor" }),
}));
vi.mock("@/lib/api/matters", () => ({
  getChecklist: async () => {
    if (mocks.assessmentPending)
      throw new ApiError(
        404,
        "checklist_snapshot_not_found",
        "Synthetic snapshot missing",
        "synthetic",
        {},
      );
    return {
      items: [
        {
          id: "item",
          group: "TITLE",
          version: 4,
          labelKey: "Synthetic original",
          physicalOriginalPolicy: "ORIGINAL_INSPECTED",
          applicability: "REQUIRED",
          collection: "RECEIVED",
          digitalReview: "UNREVIEWED",
          physicalOriginal: "UNKNOWN",
          currency: "UNKNOWN",
          consistency: "NOT_CHECKED",
          computedResolution: "OPEN",
          lifecycle: "OPEN",
          acceptedDocumentClassIds: ["rta.doc.title_certificate"],
          liveLinkCount: 1,
          inspectionHistory: [],
          waivable: false,
        },
      ],
    };
  },
}));
vi.mock("@/lib/api/documents", () => ({
  getCompleteDocumentInbox: async () => {
    if (mocks.inboxFail) throw new Error("synthetic inbox failure");
    return { documents: [] };
  },
}));
vi.mock("@/lib/api/requirements", () => ({
  listRequirementLinks: async () => [],
  requirementCommand: async (...args: unknown[]) => {
    mocks.calls.push(args);
    if (mocks.fail) {
      mocks.fail = false;
      throw new Error("network");
    }
    return {};
  },
}));
const token = async () => "synthetic-token";
it("shows guidance until a requirement is selected", async () => {
  renderWithIntl(
    <RequirementsPanel matterId="matter" getToken={token} mode="checks" />,
  );
  const guidance = await screen.findByText(
    "Select a requirement on the left to view its details and review actions.",
  );
  fireEvent.click(screen.getByRole("button", { name: "Synthetic original" }));
  expect(guidance.isConnected).toBe(false);
  expect(
    screen.getByRole("heading", { name: "Synthetic original" }),
  ).toBeTruthy();
});
it("opens the requirement recommended by the matter checklist", async () => {
  renderWithIntl(
    <RequirementsPanel
      matterId="matter"
      getToken={token}
      mode="checks"
      targetRequirementId="item"
    />,
  );
  expect(await screen.findByLabelText("Supporting document")).toBeTruthy();
  expect(
    screen.getByRole("heading", { name: "Synthetic original" }),
  ).toBeTruthy();
});
beforeEach(() => {
  mocks.calls = [];
  mocks.fail = false;
  mocks.inboxFail = false;
  mocks.assessmentPending = false;
  sessionStorage.clear();
  vi.stubGlobal("crypto", webcrypto);
});
it("guides an unassessed matter to the existing setup editor without treating it as a failed request", async () => {
  mocks.assessmentPending = true;
  renderWithIntl(
    <RequirementsPanel
      matterId="synthetic-matter"
      getToken={token}
      mode="checks"
    />,
  );
  const action = await screen.findByRole("link", {
    name: "Review matter setup",
  });
  expect(action.getAttribute("href")).toBe(
    "/matters/synthetic-matter/facts#transaction-scope",
  );
  expect(screen.queryByRole("alert")).toBeNull();
  expect(
    screen.getByText(/Requirements are still being assessed/),
  ).toBeTruthy();
});
it("keeps requirements available when the document inbox is unavailable", async () => {
  mocks.inboxFail = true;
  renderWithIntl(
    <RequirementsPanel matterId="matter" getToken={token} mode="checks" />,
  );
  expect(
    await screen.findByRole("button", { name: "Synthetic original" }),
  ).toBeTruthy();
});
it("labels all requirement dimensions and provides linking directly on Checks", async () => {
  renderWithIntl(
    <RequirementsPanel matterId="matter" getToken={token} mode="checks" />,
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "Synthetic original" }),
  );
  expect(screen.getByLabelText("Supporting document")).toBeTruthy();
  expect(
    screen.getAllByText("Physical-original inspection").length,
  ).toBeGreaterThan(0);
  expect(screen.getAllByText(/^Applicability:/).length).toBeGreaterThan(0);
});
it("records only the human inspection action and replays an ambiguous failure with exact item pin", async () => {
  mocks.fail = true;
  renderWithIntl(
    <RequirementsPanel matterId="matter" getToken={token} mode="checks" />,
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "Synthetic original" }),
  );
  fireEvent.change(screen.getByLabelText("Inspection method"), {
    target: { value: "Synthetic sighting" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Record original inspection" }),
  );
  await screen.findByRole("alert");
  fireEvent.click(
    screen.getByRole("button", { name: "Record original inspection" }),
  );
  await waitFor(() => expect(mocks.calls).toHaveLength(2));
  expect(mocks.calls[0]!.slice(2)).toEqual(mocks.calls[1]!.slice(2));
  expect(mocks.calls[0]![3]).toBe("original-inspection");
  expect(mocks.calls[0]![4]).toEqual({ method: "Synthetic sighting" });
  expect(mocks.calls[0]![5]).toBe(4);
  expect(JSON.stringify(sessionStorage)).not.toContain("Synthetic sighting");
});
it("renders Sinhala controls without offering a generic completion action", async () => {
  renderWithIntl(
    <RequirementsPanel matterId="matter" getToken={token} mode="checks" />,
    "si",
  );
  await screen.findByRole("button", { name: "Synthetic original" });
  expect(screen.queryByRole("button", { name: /mark complete/i })).toBeNull();
});
