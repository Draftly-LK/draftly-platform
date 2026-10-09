// @vitest-environment happy-dom
import { webcrypto } from "node:crypto";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import type { ApiDocumentInbox } from "@/types/rta";
const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  disposition: vi.fn(),
  read: vi.fn(),
}));
vi.mock("@/lib/api/auth", () => ({
  getMe: async () => ({ id: "synthetic-actor" }),
}));
vi.mock("@/lib/api/documents", () => ({
  createDocumentGroup: mocks.create,
  recordPageDisposition: mocks.disposition,
  getDetectedDocument: mocks.read,
}));
import { PageRecovery } from "./page-recovery";
const token = async () => null;
const inbox = {
  matterId: "synthetic-matter",
  sourceFiles: [
    {
      id: "synthetic-source",
      originalFilename: "synthetic.pdf",
      pageCount: 3,
      version: 1,
      state: "PROCESSED",
    },
  ],
  documents: [],
  pageAccounting: [
    {
      sourceFileId: "synthetic-source",
      pageCount: 3,
      unclaimedPageNumbers: [2, 3],
      overlappingPageNumbers: [],
      blankPageNumbers: [],
      unsupportedPageNumbers: [],
      complete: false,
      manualReviewRequired: true,
    },
  ],
} as unknown as ApiDocumentInbox;
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  vi.stubGlobal("crypto", webcrypto);
});
it("recovers a second group from unclaimed pages with one persistent command", async () => {
  mocks.create.mockResolvedValue({ id: "synthetic-new" });
  mocks.read.mockResolvedValue({
    id: "synthetic-new",
    matterId: "synthetic-matter",
  });
  const changed = vi.fn();
  renderWithIntl(
    <PageRecovery getToken={token} inbox={inbox} onChange={changed} />,
  );
  expect(screen.getByText("Pages needing a group: 2, 3")).toBeTruthy();
  expect(screen.queryByText("Every page is accounted for")).toBeNull();
  fireEvent.click(
    screen.getByRole("button", { name: "Group unclaimed pages" }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Create document from these pages" }),
  );
  await waitFor(() => expect(mocks.create).toHaveBeenCalled());
  expect(mocks.create.mock.calls[0]![2]).toEqual({
    fragments: [
      {
        sourceFileId: "synthetic-source",
        pageStart: 2,
        pageEnd: 3,
        orderInDocument: 0,
      },
    ],
  });
  expect(mocks.create.mock.calls[0]![3]).toEqual(expect.any(String));
  expect(
    await screen.findByRole("link", { name: "Review this document" }),
  ).toBeTruthy();
  expect(changed).toHaveBeenCalledOnce();
});
it("keeps unsupported pages in manual review and records a reason for each disposition", async () => {
  const unsupported = {
    ...inbox,
    pageAccounting: [
      {
        ...inbox.pageAccounting![0]!,
        unclaimedPageNumbers: [],
        unsupportedPageNumbers: [2],
        complete: true,
        manualReviewRequired: true,
      },
    ],
  };
  renderWithIntl(
    <PageRecovery getToken={token} inbox={unsupported} onChange={vi.fn()} />,
  );
  expect(
    screen.getByText("Unsupported pages still need manual review: 2"),
  ).toBeTruthy();
  expect(screen.queryByText("Every page is accounted for")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Record page status" }));
  const save = screen.getByRole("button", { name: "Save page status" });
  expect(save.hasAttribute("disabled")).toBe(true);
  fireEvent.change(screen.getByLabelText("Reason"), {
    target: { value: "SYNTHETIC page is blank" },
  });
  fireEvent.change(screen.getByLabelText("Page number"), {
    target: { value: "2" },
  });
  fireEvent.click(save);
  await waitFor(() => expect(mocks.disposition).toHaveBeenCalled());
  expect(mocks.disposition.mock.calls[0]!.slice(1, 4)).toEqual([
    "synthetic-source",
    { pageNumber: 2, disposition: "blank", reason: "SYNTHETIC page is blank" },
    1,
  ]);
});
