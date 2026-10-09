// @vitest-environment happy-dom
import { webcrypto } from "node:crypto";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import type { ApiDetectedDocument } from "@/types/rta";

const mocks = vi.hoisted(() => ({
  read: vi.fn(),
  boundary: vi.fn(),
  refresh: vi.fn(),
  inbox: vi.fn(),
  history: vi.fn(),
}));
vi.mock("@/lib/api/auth", () => ({
  getMe: async () => ({ id: "synthetic-actor" }),
}));
vi.mock("@/lib/api/rta", () => ({
  getRtaDocumentClasses: async () => ({ classes: [] }),
}));
vi.mock("@/lib/api/documents", () => ({
  getDetectedDocument: mocks.read,
  recordBoundaryDecision: mocks.boundary,
  recordClassificationDecision: vi.fn(),
  refreshDocumentExtraction: mocks.refresh,
  getCompleteDocumentInbox: mocks.inbox,
  getDocumentInterpretations: mocks.history,
}));
import { DocumentDecisions } from "./document-decisions";
import { ApiError } from "@/lib/api/client";
const token = async () => null;
const current = {
  id: "synthetic-doc",
  matterId: "synthetic-matter",
  classId: "rta.doc.nic",
  classStatus: "LAWYER_CONFIRMED",
  boundaryStatus: "CONFIRMED",
  version: 3,
  interpretationGeneration: 2,
  extractionState: "refresh_required",
  fragments: [
    {
      sourceFileId: "synthetic-source",
      pageStart: 1,
      pageEnd: 3,
      orderInDocument: 0,
    },
  ],
} as ApiDetectedDocument;
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  vi.stubGlobal("crypto", webcrypto);
  mocks.read.mockResolvedValue(current);
  mocks.inbox.mockResolvedValue({
    sourceFiles: [
      {
        id: "synthetic-source",
        originalFilename: "synthetic.pdf",
        pageCount: 3,
      },
    ],
    documents: [current],
  });
  mocks.history.mockResolvedValue({
    currentGeneration: 2,
    snapshots: [],
    refreshRuns: [],
  });
});
it("edits exact ranges and reads current state after a historical successful replay", async () => {
  const changed = vi.fn();
  mocks.boundary.mockResolvedValue({
    ...current,
    extractionState: "current",
    interpretationGeneration: 1,
  });
  renderWithIntl(
    <DocumentDecisions
      getToken={token}
      matterId="synthetic-matter"
      documentId="synthetic-doc"
      onChange={changed}
    />,
  );
  fireEvent.change(await screen.findByLabelText("Last page"), {
    target: { value: "1" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save page grouping" }));
  await waitFor(() => expect(mocks.boundary).toHaveBeenCalled());
  expect(mocks.boundary.mock.calls[0]![2].fragments).toEqual([
    {
      sourceFileId: "synthetic-source",
      pageStart: 1,
      pageEnd: 1,
      orderInDocument: 0,
    },
  ]);
  await waitFor(() => expect(mocks.read).toHaveBeenCalledTimes(2));
  expect(changed.mock.calls.at(-1)?.[0]).toEqual(current);
});
it("retains refresh key and old precondition through an ambiguous failure and remount", async () => {
  mocks.refresh
    .mockRejectedValueOnce(new Error("synthetic network loss"))
    .mockResolvedValue(current);
  const view = renderWithIntl(
    <DocumentDecisions
      getToken={token}
      matterId="synthetic-matter"
      documentId="synthetic-doc"
    />,
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "Refresh extraction" }),
  );
  await screen.findByRole("alert");
  const first = mocks.refresh.mock.calls[0]!;
  view.unmount();
  mocks.read.mockResolvedValue({ ...current, version: 4 });
  renderWithIntl(
    <DocumentDecisions
      getToken={token}
      matterId="synthetic-matter"
      documentId="synthetic-doc"
    />,
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "Refresh extraction" }),
  );
  await waitFor(() => expect(mocks.refresh).toHaveBeenCalledTimes(2));
  expect(first[3]).toEqual(expect.any(String));
  expect(mocks.refresh.mock.calls[1]!.slice(2)).toEqual(first.slice(2));
});

it("renews a definitively refused stale precondition after a current read", async () => {
  mocks.refresh
    .mockRejectedValueOnce(
      new ApiError(412, "stale", "SYNTHETIC stale version", "synthetic", {}),
    )
    .mockResolvedValue(current);
  renderWithIntl(
    <DocumentDecisions
      getToken={token}
      matterId="synthetic-matter"
      documentId="synthetic-doc"
    />,
  );
  const button = await screen.findByRole("button", {
    name: "Refresh extraction",
  });
  mocks.read.mockResolvedValue({ ...current, version: 5 });
  fireEvent.click(button);
  await screen.findByRole("alert");
  await waitFor(() => expect(button.hasAttribute("disabled")).toBe(false));
  const first = mocks.refresh.mock.calls[0]!;
  fireEvent.click(button);
  await waitFor(() => expect(mocks.refresh).toHaveBeenCalledTimes(2));
  expect(mocks.refresh.mock.calls[1]![2]).toBe(5);
  expect(mocks.refresh.mock.calls[1]![3]).not.toBe(first[3]);
});
