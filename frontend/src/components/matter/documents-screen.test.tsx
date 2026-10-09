// @vitest-environment happy-dom
import { webcrypto } from "node:crypto";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import type { ApiDocumentInbox, ApiSourceFile } from "@/types/rta";

const mocks = vi.hoisted(() => ({
  files: [] as unknown[],
  uploads: [] as string[],
  keys: [] as string[],
  failNext: false,
  documents: [] as unknown[],
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, isApiEnabled: () => true };
});
vi.mock("@/lib/api/use-token-provider", () => ({
  useTokenProvider: () => async () => null,
}));
vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("@/lib/api/matters", () => ({ getChecklist: async () => ({ items: [] }) }));
vi.mock("@/lib/api/documents", () => ({
  getCompleteDocumentInbox: async (): Promise<ApiDocumentInbox> =>
    ({
      matterId: "m1",
      sourceFiles: mocks.files as ApiSourceFile[],
      documents: mocks.documents,
      boundaryReviewDocumentIds: [],
      classificationReviewDocumentIds: [],
      unidentifiedDocumentIds: [],
      unprocessedSourceFileIds: (mocks.files as ApiSourceFile[]).map(
        (file) => file.id,
      ),
      page: { hasMore: false, nextCursor: null },
    }) as unknown as ApiDocumentInbox,
  uploadSourceFile: async (
    _getToken: unknown,
    _matterId: string,
    file: File,
    key: string,
  ) => {
    mocks.keys.push(key);
    if (mocks.failNext) {
      mocks.failNext = false;
      throw new Error("network");
    }
    mocks.uploads.push(file.name);
    const stored = {
      id: `sf-${mocks.files.length}`,
      originalFilename: file.name,
      state: "STORED",
      pageCount: 0,
    };
    mocks.files.push(stored);
    return stored;
  },
}));

import { DocumentsScreen } from "./documents-screen";

const pdf = (name: string) =>
  new File(["%PDF-synthetic"], name, { type: "application/pdf" });

function choose(files: File[]) {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("no file input");
  Object.defineProperty(input, "files", { value: files, configurable: true });
  fireEvent.change(input);
}

vi.mock("@/lib/api/auth", () => ({
  getMe: async () => ({ id: "synthetic-actor" }),
}));

beforeEach(() => {
  sessionStorage.clear();
  vi.stubGlobal("crypto", webcrypto);
  mocks.files = [];
  mocks.uploads = [];
  mocks.keys = [];
  mocks.failNext = false;
  mocks.documents = [];
});

describe("DocumentsScreen upload", () => {
  it("keeps a confirmed group reachable for correction and counts its original pages", async () => {
    mocks.documents = [
      {
        id: "synthetic-doc",
        classId: "rta.doc.nic",
        classStatus: "LAWYER_CONFIRMED",
        boundaryStatus: "CONFIRMED",
        extractionState: "refresh_required",
        fragments: [
          { sourceFileId: "synthetic-source", pageStart: 1, pageEnd: 3 },
        ],
        spansMultipleSources: false,
      },
    ];
    renderWithIntl(<DocumentsScreen matterId="m1" />);
    const link = await screen.findByRole("link", { name: /Review/ });
    expect(link.getAttribute("href")).toBe(
      "/matters/m1/documents/synthetic-doc/review",
    );
    expect(screen.getByText("3")).toBeTruthy();
    expect(
      screen.getByText(
        "The document changed. Previous extraction and its dependent facts are historical until refreshed and reviewed.",
      ),
    ).toBeTruthy();
  });
  it("reuses an ambiguous upload key on remount but creates a new intent after success", async () => {
    const view = renderWithIntl(<DocumentsScreen matterId="m1" />);
    await screen.findByRole("button", { name: /Upload documents/ });
    mocks.failNext = true;
    choose([pdf("synthetic-retry.pdf")]);
    await screen.findByRole("alert");
    const first = mocks.keys[0];
    expect(first).toEqual(expect.any(String));
    view.unmount();
    renderWithIntl(<DocumentsScreen matterId="m1" />);
    await screen.findByRole("button", { name: /Upload documents/ });
    choose([pdf("synthetic-retry.pdf")]);
    await screen.findByText("1 file added. Process it to read its contents.");
    expect(mocks.keys[1]).toBe(first);
    choose([pdf("synthetic-retry.pdf")]);
    await waitFor(() => expect(mocks.keys.length).toBe(3));
    expect(mocks.keys[2]).not.toBe(first);
  });
  it("offers an upload on an empty matter and says what to upload", async () => {
    renderWithIntl(<DocumentsScreen matterId="m1" />);
    const button = await screen.findByRole("button", {
      name: /Upload documents/,
    });
    expect(button.className).toContain("bg-primary-bg");
    expect(
      screen.getByText(
        "No documents yet. Upload the evidence this matter needs.",
      ),
    ).toBeTruthy();
    expect(screen.getByText(/Synthetic documents only/)).toBeTruthy();
  });

  it("uploads the chosen files, then lists them as waiting to be processed", async () => {
    renderWithIntl(<DocumentsScreen matterId="m1" />);
    await screen.findByRole("button", { name: /Upload documents/ });
    choose([pdf("synthetic-nic.pdf"), pdf("synthetic-deed.pdf")]);
    expect(
      await screen.findByText(
        "2 files added. Process them to read their contents.",
      ),
    ).toBeTruthy();
    expect(mocks.uploads).toEqual(["synthetic-nic.pdf", "synthetic-deed.pdf"]);
    expect(
      await screen.findByText("2 files waiting to be processed"),
    ).toBeTruthy();
    expect(screen.getByText("synthetic-deed.pdf")).toBeTruthy();
    // With files waiting, processing is the next step, so upload steps back to secondary.
    expect(
      screen.getByRole("button", { name: /Upload documents/ }).className,
    ).not.toContain("bg-primary-bg");
  });

  it("says when a file could not be uploaded, and still keeps the ones that did", async () => {
    renderWithIntl(<DocumentsScreen matterId="m1" />);
    await screen.findByRole("button", { name: /Upload documents/ });
    mocks.failNext = true;
    choose([pdf("broken.pdf"), pdf("synthetic-plan.pdf")]);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("1 file could not be uploaded.");
    await waitFor(() =>
      expect(screen.getByText("synthetic-plan.pdf")).toBeTruthy(),
    );
  });
});
