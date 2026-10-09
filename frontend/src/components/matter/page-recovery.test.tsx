// @vitest-environment happy-dom
import { webcrypto } from "node:crypto";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { useState } from "react";
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
import { ApiError } from "@/lib/api/client";
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

it.each(["group", "page"])(
  "pins %s edits before the first POST until current-state renewal",
  async (kind) => {
    function Host() {
      const [value, setValue] = useState(inbox);
      return (
        <>
          <button
            onClick={() =>
              setValue({
                ...inbox,
                sourceFiles: [{ ...inbox.sourceFiles[0]!, version: 2 }],
              })
            }
          >
            Change source
          </button>
          <PageRecovery getToken={token} inbox={value} onChange={vi.fn()} />
        </>
      );
    }
    renderWithIntl(<Host />);
    fireEvent.click(
      screen.getByRole("button", {
        name: kind === "group" ? "Group unclaimed pages" : "Record page status",
      }),
    );
    if (kind === "page")
      fireEvent.change(screen.getByLabelText("Reason"), {
        target: { value: "SYNTHETIC reviewed page" },
      });
    fireEvent.click(screen.getByRole("button", { name: "Change source" }));
    const save = screen.getByRole("button", {
      name:
        kind === "group"
          ? "Create document from these pages"
          : "Save page status",
    });
    expect(save.hasAttribute("disabled")).toBe(true);
    fireEvent.click(save);
    expect(mocks.create).not.toHaveBeenCalled();
    expect(mocks.disposition).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Review current document state" }),
    );
    if (kind === "page") {
      expect((screen.getByLabelText("Reason") as HTMLInputElement).value).toBe(
        "",
      );
      await waitFor(() =>
        expect(document.activeElement).toBe(
          screen.getByLabelText("Page number"),
        ),
      );
      fireEvent.change(screen.getByLabelText("Reason"), {
        target: { value: "SYNTHETIC renewed page" },
      });
      fireEvent.click(save);
      await waitFor(() => expect(mocks.disposition).toHaveBeenCalled());
      expect(mocks.disposition.mock.calls[0]![3]).toBe(2);
    } else {
      expect(save.hasAttribute("disabled")).toBe(false);
      await waitFor(() =>
        expect(document.activeElement).toBe(screen.getByRole("combobox")),
      );
    }
  },
);

it("requires renewal after a definite page-status refusal", async () => {
  mocks.disposition.mockRejectedValueOnce(
    new ApiError(412, "stale", "SYNTHETIC stale version", "synthetic", {}),
  );
  renderWithIntl(
    <PageRecovery getToken={token} inbox={inbox} onChange={vi.fn()} />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Record page status" }));
  fireEvent.change(screen.getByLabelText("Reason"), {
    target: { value: "SYNTHETIC page" },
  });
  const save = screen.getByRole("button", { name: "Save page status" });
  fireEvent.click(save);
  await screen.findByRole("alert");
  expect(save.hasAttribute("disabled")).toBe(true);
  expect(
    screen.getByRole("button", { name: "Review current document state" }),
  ).toBeTruthy();
});

it.each(["membership", "retirement-version", "missing-source", "page-status"])(
  "refuses a stale page decision when %s changes without a new source version",
  async (change) => {
    const member = {
      id: "synthetic-member",
      version: 1,
      fragments: [
        { sourceFileId: "synthetic-source", pageStart: 2, pageEnd: 2 },
      ],
    };
    const initial = { ...inbox, documents: [member] } as ApiDocumentInbox;
    function Host() {
      const [value, setValue] = useState(initial);
      return (
        <>
          <button
            onClick={() =>
              setValue({
                ...initial,
                sourceFiles:
                  change === "missing-source" ? [] : initial.sourceFiles,
                documents: [
                  {
                    ...member,
                    version: change === "retirement-version" ? 2 : 1,
                    fragments:
                      change === "membership"
                        ? [{ ...member.fragments[0], pageEnd: 3 }]
                        : member.fragments,
                  },
                ],
                pageAccounting:
                  change === "page-status"
                    ? [
                        {
                          ...initial.pageAccounting![0]!,
                          unclaimedPageNumbers: [3],
                          blankPageNumbers: [2],
                        },
                      ]
                    : initial.pageAccounting,
              } as ApiDocumentInbox)
            }
          >
            Change membership
          </button>
          <PageRecovery getToken={token} inbox={value} onChange={vi.fn()} />
        </>
      );
    }
    renderWithIntl(<Host />);
    fireEvent.click(screen.getByRole("button", { name: "Record page status" }));
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.change(screen.getByLabelText("Reason"), {
      target: { value: "SYNTHETIC reviewed retirement" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Change membership" }));
    expect(
      screen
        .getByRole("button", { name: "Save page status" })
        .hasAttribute("disabled"),
    ).toBe(true);
    expect(mocks.disposition).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Review current document state" }),
    );
    expect(
      (screen.queryByRole("checkbox") as HTMLInputElement | null)?.checked,
    ).not.toBe(true);
    if (change === "missing-source")
      expect(
        screen.queryByRole("button", { name: "Save page status" }),
      ).toBeNull();
    else
      expect((screen.getByLabelText("Reason") as HTMLInputElement).value).toBe(
        "",
      );
  },
);

it("replays an ambiguous page command with its original key and precondition after new props arrive", async () => {
  mocks.disposition
    .mockRejectedValueOnce(new Error("SYNTHETIC lost response"))
    .mockResolvedValue(inbox.sourceFiles[0]);
  function Host() {
    const [value, setValue] = useState(inbox);
    return (
      <>
        <button
          onClick={() =>
            setValue({
              ...inbox,
              sourceFiles: [{ ...inbox.sourceFiles[0]!, version: 2 }],
            })
          }
        >
          Change source
        </button>
        <PageRecovery getToken={token} inbox={value} onChange={vi.fn()} />
      </>
    );
  }
  renderWithIntl(<Host />);
  fireEvent.click(screen.getByRole("button", { name: "Record page status" }));
  fireEvent.change(screen.getByLabelText("Reason"), {
    target: { value: "SYNTHETIC ambiguous page" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save page status" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Change source" }));
  fireEvent.click(
    screen.getByRole("button", { name: "Retry pending command" }),
  );
  await waitFor(() => expect(mocks.disposition).toHaveBeenCalledTimes(2));
  expect(mocks.disposition.mock.calls[1]!.slice(1)).toEqual(
    mocks.disposition.mock.calls[0]!.slice(1),
  );
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

it("does not offer another group command when creation succeeded but the current read failed", async () => {
  mocks.create.mockResolvedValue({ id: "synthetic-new" });
  mocks.read.mockRejectedValue(new Error("SYNTHETIC current read unavailable"));
  const changed = vi.fn();
  renderWithIntl(
    <PageRecovery getToken={token} inbox={inbox} onChange={changed} />,
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Group unclaimed pages" }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Create document from these pages" }),
  );
  await screen.findByRole("alert");
  expect(
    screen.queryByRole("button", { name: "Retry pending command" }),
  ).toBeNull();
  expect(
    screen
      .getByRole("button", { name: "Create document from these pages" })
      .hasAttribute("disabled"),
  ).toBe(true);
  expect(changed).toHaveBeenCalled();
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

it("requires processing before offering page decisions for an original with unknown length", () => {
  const unknown = {
    ...inbox,
    sourceFiles: [{ ...inbox.sourceFiles[0]!, pageCount: null }],
    pageAccounting: [
      {
        ...inbox.pageAccounting![0]!,
        pageCount: null,
        unclaimedPageNumbers: [],
      },
    ],
  };
  renderWithIntl(
    <PageRecovery getToken={token} inbox={unknown} onChange={vi.fn()} />,
  );
  expect(
    screen.getByText(
      "Page count is unknown. Process the original before grouping its pages.",
    ),
  ).toBeTruthy();
  expect(
    screen.queryByRole("button", { name: "Group unclaimed pages" }),
  ).toBeNull();
  expect(
    screen.queryByRole("button", { name: "Record page status" }),
  ).toBeNull();
  expect(mocks.create).not.toHaveBeenCalled();
  expect(mocks.disposition).not.toHaveBeenCalled();
});

it("shows conflicting and out-of-bounds pages even when no pages remain unclaimed", () => {
  const conflicted = {
    ...inbox,
    pageAccounting: [
      {
        ...inbox.pageAccounting![0]!,
        unclaimedPageNumbers: [],
        overlappingPageNumbers: [2],
        outOfBoundsPageNumbers: [4],
        blankPageNumbers: [1],
      },
    ],
  };
  renderWithIntl(
    <PageRecovery getToken={token} inbox={conflicted} onChange={vi.fn()} />,
  );
  expect(screen.getByText("Pages in conflicting groups: 2")).toBeTruthy();
  expect(
    screen.getByText("Grouping refers to pages outside the original: 4"),
  ).toBeTruthy();
  expect(screen.getByText("Marked blank: 1")).toBeTruthy();
  expect(screen.queryByText("Every page is accounted for")).toBeNull();
  expect(
    screen.queryByRole("button", { name: "Group unclaimed pages" }),
  ).toBeNull();
  expect(
    screen.getByRole("button", { name: "Record page status" }),
  ).toBeTruthy();
});

it("marks reconciled pages as accounted while retaining the ability to correct their status", () => {
  const complete = {
    ...inbox,
    pageAccounting: [
      {
        ...inbox.pageAccounting![0]!,
        unclaimedPageNumbers: [],
        complete: true,
        manualReviewRequired: false,
      },
    ],
  };
  renderWithIntl(
    <PageRecovery getToken={token} inbox={complete} onChange={vi.fn()} />,
  );
  expect(screen.getByText("Every page is accounted for")).toBeTruthy();
  expect(
    screen.queryByRole("button", { name: "Group unclaimed pages" }),
  ).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Record page status" }));
  expect((screen.getByLabelText("Page number") as HTMLInputElement).value).toBe(
    "1",
  );
  expect(
    screen
      .getByRole("button", { name: "Save page status" })
      .hasAttribute("disabled"),
  ).toBe(true);
});

it("retires only the explicitly selected current one-page group with its reviewed version", async () => {
  const member = {
    id: "synthetic-single-page",
    version: 7,
    fragments: [{ sourceFileId: "synthetic-source", pageStart: 2, pageEnd: 2 }],
  };
  const grouped = {
    ...inbox,
    documents: [
      member,
      {
        ...member,
        id: "synthetic-superseded",
        versionRelationship: "SUPERSEDED",
      },
      {
        ...member,
        id: "synthetic-multi-page",
        fragments: [{ ...member.fragments[0], pageEnd: 3 }],
      },
      {
        ...member,
        id: "synthetic-other-source",
        fragments: [
          { ...member.fragments[0], sourceFileId: "synthetic-other" },
        ],
      },
      { ...member, id: "synthetic-no-pages", fragments: [] },
    ],
  } as ApiDocumentInbox;
  mocks.disposition.mockResolvedValue(inbox.sourceFiles[0]);
  renderWithIntl(
    <PageRecovery getToken={token} inbox={grouped} onChange={vi.fn()} />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Record page status" }));
  expect(screen.getAllByRole("checkbox")).toHaveLength(1);
  const selected = screen.getByRole("checkbox") as HTMLInputElement;
  fireEvent.click(selected);
  expect(selected.checked).toBe(true);
  fireEvent.click(selected);
  expect(selected.checked).toBe(false);
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "review_required" },
  });
  expect(screen.queryByRole("checkbox")).toBeNull();
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "blank" },
  });
  expect((screen.getByRole("checkbox") as HTMLInputElement).checked).toBe(
    false,
  );
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.change(screen.getByLabelText("Reason"), {
    target: { value: "  SYNTHETIC reviewed blank page  " },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save page status" }));
  await waitFor(() => expect(mocks.disposition).toHaveBeenCalledOnce());
  expect(mocks.disposition.mock.calls[0]!.slice(1, 4)).toEqual([
    "synthetic-source",
    {
      pageNumber: 2,
      disposition: "blank",
      reason: "SYNTHETIC reviewed blank page",
      retireDocuments: [{ documentId: "synthetic-single-page", version: 7 }],
    },
    1,
  ]);
});

it.each(["0", "4", "1.5"])(
  "refuses page %s outside the original's integer page range",
  (page) => {
    renderWithIntl(
      <PageRecovery getToken={token} inbox={inbox} onChange={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Record page status" }));
    fireEvent.change(screen.getByLabelText("Reason"), {
      target: { value: "SYNTHETIC page review" },
    });
    fireEvent.change(screen.getByLabelText("Page number"), {
      target: { value: page },
    });
    const save = screen.getByRole("button", { name: "Save page status" });
    expect(save.hasAttribute("disabled")).toBe(true);
    fireEvent.click(save);
    expect(mocks.disposition).not.toHaveBeenCalled();
  },
);

it("renews a removed page to the current unsupported page and current source version", async () => {
  function Host() {
    const [value, setValue] = useState(inbox);
    return (
      <>
        <button
          onClick={() =>
            setValue({
              ...inbox,
              sourceFiles: [
                { ...inbox.sourceFiles[0]!, pageCount: 1, version: 2 },
              ],
              pageAccounting: [
                {
                  ...inbox.pageAccounting![0]!,
                  pageCount: 1,
                  unclaimedPageNumbers: [],
                  unsupportedPageNumbers: [1],
                },
              ],
            })
          }
        >
          Refresh corrected original
        </button>
        <PageRecovery getToken={token} inbox={value} onChange={vi.fn()} />
      </>
    );
  }
  renderWithIntl(<Host />);
  fireEvent.click(screen.getByRole("button", { name: "Record page status" }));
  fireEvent.change(screen.getByLabelText("Page number"), {
    target: { value: "3" },
  });
  fireEvent.change(screen.getByLabelText("Reason"), {
    target: { value: "SYNTHETIC obsolete review" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Refresh corrected original" }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Review current document state" }),
  );
  expect((screen.getByLabelText("Page number") as HTMLInputElement).value).toBe(
    "1",
  );
  expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe(
    "unsupported",
  );
  expect((screen.getByLabelText("Reason") as HTMLInputElement).value).toBe("");
  fireEvent.change(screen.getByLabelText("Reason"), {
    target: { value: "SYNTHETIC renewed unsupported page" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save page status" }));
  await waitFor(() => expect(mocks.disposition).toHaveBeenCalledOnce());
  expect(mocks.disposition.mock.calls[0]!.slice(1, 4)).toEqual([
    "synthetic-source",
    {
      pageNumber: 1,
      disposition: "unsupported",
      reason: "SYNTHETIC renewed unsupported page",
    },
    2,
  ]);
});

it("removes a proposed group on renewal when its pages have already been accounted for", () => {
  function Host() {
    const [value, setValue] = useState(inbox);
    return (
      <>
        <button
          onClick={() =>
            setValue({
              ...inbox,
              pageAccounting: [
                {
                  ...inbox.pageAccounting![0]!,
                  unclaimedPageNumbers: [],
                  blankPageNumbers: [2, 3],
                },
              ],
            })
          }
        >
          Refresh accounted pages
        </button>
        <PageRecovery getToken={token} inbox={value} onChange={vi.fn()} />
      </>
    );
  }
  renderWithIntl(<Host />);
  fireEvent.click(
    screen.getByRole("button", { name: "Group unclaimed pages" }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Refresh accounted pages" }),
  );
  expect(
    screen
      .getByRole("button", { name: "Create document from these pages" })
      .hasAttribute("disabled"),
  ).toBe(true);
  fireEvent.click(
    screen.getByRole("button", { name: "Review current document state" }),
  );
  expect(
    screen.queryByRole("button", { name: "Create document from these pages" }),
  ).toBeNull();
  expect(screen.getByText("Marked blank: 2, 3")).toBeTruthy();
  expect(mocks.create).not.toHaveBeenCalled();
});
