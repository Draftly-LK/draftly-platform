// @vitest-environment happy-dom
import { webcrypto } from "node:crypto";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import { RequirementsPanel } from "./requirements-panel";

const mocks = vi.hoisted(() => ({ calls: [] as unknown[][], fail: false }));
vi.mock("@/lib/api/auth", () => ({
  getMe: async () => ({ id: "synthetic-actor" }),
}));
vi.mock("@/lib/api/matters", () => ({
  getChecklist: async () => ({
    items: [
      {
        id: "item",
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
  }),
}));
vi.mock("@/lib/api/documents", () => ({
  getCompleteDocumentInbox: async () => ({ documents: [] }),
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
beforeEach(() => {
  mocks.calls = [];
  mocks.fail = false;
  sessionStorage.clear();
  vi.stubGlobal("crypto", webcrypto);
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
