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
  classify: vi.fn(),
}));
vi.mock("@/lib/api/auth", () => ({
  getMe: async () => ({ id: "synthetic-actor" }),
}));
vi.mock("@/lib/api/rta", () => ({
  getRtaDocumentClasses: async () => ({
    classes: [
      { id: "rta.doc.nic", labelKey: "synthetic.nic.label" },
      { id: "rta.doc.title", labelKey: "synthetic.title.label" },
    ],
  }),
}));
vi.mock("@/lib/api/documents", () => ({
  getDetectedDocument: mocks.read,
  recordBoundaryDecision: mocks.boundary,
  recordClassificationDecision: mocks.classify,
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
  await waitFor(() => expect(mocks.read).toHaveBeenCalledTimes(3));
  expect(changed.mock.calls.at(-1)?.[0]).toEqual(current);
});

it.each(["class", "boundary"] as const)(
  "requires deliberate renewal after a refused %s edit",
  async (kind) => {
    const command = kind === "class" ? mocks.classify : mocks.boundary;
    command
      .mockImplementationOnce(async () => {
        mocks.read.mockResolvedValue({
          ...current,
          version: 5,
          fragments: [{ ...current.fragments[0], pageEnd: 2 }],
        });
        throw new ApiError(
          412,
          "stale",
          "SYNTHETIC stale version",
          "synthetic",
          {},
        );
      })
      .mockResolvedValue(current);
    renderWithIntl(
      <DocumentDecisions
        getToken={token}
        matterId="synthetic-matter"
        documentId="synthetic-doc"
      />,
    );
    await screen.findByLabelText("Last page");
    if (kind === "class")
      fireEvent.change(
        screen.getByRole("combobox", { name: "Select document class" }),
        { target: { value: "rta.doc.title" } },
      );
    else
      fireEvent.change(screen.getByLabelText("Last page"), {
        target: { value: "1" },
      });
    const save = () =>
      screen.getByRole("button", {
        name: kind === "class" ? "Confirm type" : "Save page grouping",
      });
    fireEvent.click(save());
    await screen.findByRole("alert");
    expect(save().hasAttribute("disabled")).toBe(true);
    expect(command).toHaveBeenCalledTimes(1);
    fireEvent.click(
      screen.getByRole("button", { name: "Review current document state" }),
    );
    await waitFor(() =>
      expect(
        (screen.getByLabelText("Last page") as HTMLInputElement).value,
      ).toBe("2"),
    );
    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole("combobox", { name: "Select document class" }),
      ),
    );
    if (kind === "class")
      fireEvent.change(
        screen.getByRole("combobox", { name: "Select document class" }),
        { target: { value: "rta.doc.title" } },
      );
    else
      fireEvent.change(screen.getByLabelText("Last page"), {
        target: { value: "1" },
      });
    fireEvent.click(save());
    await waitFor(() => expect(command).toHaveBeenCalledTimes(2));
    expect(command.mock.calls[1]![3]).toBe(5);
    expect(command.mock.calls[1]![4]).not.toBe(command.mock.calls[0]![4]);
  },
);

it("refuses a first grouping POST when the reviewed document has changed", async () => {
  renderWithIntl(
    <DocumentDecisions
      getToken={token}
      matterId="synthetic-matter"
      documentId="synthetic-doc"
    />,
  );
  fireEvent.change(await screen.findByLabelText("Last page"), {
    target: { value: "1" },
  });
  mocks.read.mockResolvedValue({ ...current, version: 6 });
  fireEvent.click(screen.getByRole("button", { name: "Save page grouping" }));
  await screen.findByRole("button", { name: "Review current document state" });
  expect(mocks.boundary).not.toHaveBeenCalled();
  expect(
    screen
      .getByRole("button", { name: "Save page grouping" })
      .hasAttribute("disabled"),
  ).toBe(true);
});

it("replays an ambiguous edited grouping with the original key and original version", async () => {
  mocks.boundary
    .mockImplementationOnce(async () => {
      mocks.read.mockResolvedValue({ ...current, version: 7 });
      throw new Error("SYNTHETIC lost response");
    })
    .mockResolvedValue(current);
  renderWithIntl(
    <DocumentDecisions
      getToken={token}
      matterId="synthetic-matter"
      documentId="synthetic-doc"
    />,
  );
  fireEvent.change(await screen.findByLabelText("Last page"), {
    target: { value: "1" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save page grouping" }));
  await screen.findByRole("alert");
  const retry = await screen.findByRole("button", {
    name: "Retry pending command",
  });
  await waitFor(() => expect(retry.hasAttribute("disabled")).toBe(false));
  fireEvent.click(retry);
  await waitFor(() => expect(mocks.boundary).toHaveBeenCalledTimes(2));
  expect(mocks.boundary.mock.calls[1]!.slice(1)).toEqual(
    mocks.boundary.mock.calls[0]!.slice(1),
  );
});

it("pins a selected retirement from another original even when the edited document version is unchanged", async () => {
  const queue = await mocks.inbox();
  const member = {
    ...current,
    id: "synthetic-other",
    version: 1,
    fragments: [
      {
        ...current.fragments[0],
        sourceFileId: "synthetic-other-source",
        pageEnd: 1,
      },
    ],
  };
  const initial = {
    ...queue,
    sourceFiles: [
      ...queue.sourceFiles,
      {
        ...queue.sourceFiles[0],
        id: "synthetic-other-source",
        originalFilename: "synthetic other.pdf",
      },
    ],
    documents: [current, member],
  };
  mocks.inbox.mockResolvedValue(initial);
  renderWithIntl(
    <DocumentDecisions
      getToken={token}
      matterId="synthetic-matter"
      documentId="synthetic-doc"
    />,
  );
  fireEvent.click(await screen.findByRole("checkbox"));
  mocks.inbox.mockResolvedValue({
    ...initial,
    documents: [current, { ...member, version: 2 }],
  });
  fireEvent.click(screen.getByRole("button", { name: "Save page grouping" }));
  fireEvent.click(
    await screen.findByRole("button", {
      name: "Review current document state",
    }),
  );
  await waitFor(() =>
    expect((screen.getByRole("checkbox") as HTMLInputElement).checked).toBe(
      false,
    ),
  );
  expect(mocks.boundary).not.toHaveBeenCalled();
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
  expect(
    screen
      .getByRole("button", { name: "Save page grouping" })
      .hasAttribute("disabled"),
  ).toBe(true);
  const first = mocks.refresh.mock.calls[0]!;
  fireEvent.click(button);
  await waitFor(() => expect(mocks.refresh).toHaveBeenCalledTimes(2));
  expect(mocks.refresh.mock.calls[1]![2]).toBe(5);
  expect(mocks.refresh.mock.calls[1]![3]).not.toBe(first[3]);
});
