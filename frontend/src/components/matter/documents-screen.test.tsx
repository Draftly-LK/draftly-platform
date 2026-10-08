// @vitest-environment happy-dom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import type { ApiDocumentInbox, ApiSourceFile } from "@/types/rta";

const mocks = vi.hoisted(() => ({
  files: [] as unknown[],
  uploads: [] as string[],
  failNext: false,
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, isApiEnabled: () => true };
});
vi.mock("@/lib/api/use-token-provider", () => ({ useTokenProvider: () => async () => null }));
vi.mock("@/components/shell/app-shell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/lib/api/documents", () => ({
  getDocumentInbox: async (): Promise<ApiDocumentInbox> =>
    ({
      matterId: "m1",
      sourceFiles: mocks.files as ApiSourceFile[],
      documents: [],
      boundaryReviewDocumentIds: [],
      classificationReviewDocumentIds: [],
      unidentifiedDocumentIds: [],
      unprocessedSourceFileIds: (mocks.files as ApiSourceFile[]).map((file) => file.id),
      page: { hasMore: false, nextCursor: null },
    }) as unknown as ApiDocumentInbox,
  uploadSourceFile: async (_getToken: unknown, _matterId: string, file: File) => {
    if (mocks.failNext) {
      mocks.failNext = false;
      throw new Error("network");
    }
    mocks.uploads.push(file.name);
    const stored = { id: `sf-${mocks.files.length}`, originalFilename: file.name, state: "STORED", pageCount: 0 };
    mocks.files.push(stored);
    return stored;
  },
}));

import { DocumentsScreen } from "./documents-screen";

const pdf = (name: string) => new File(["%PDF-synthetic"], name, { type: "application/pdf" });

function choose(files: File[]) {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("no file input");
  Object.defineProperty(input, "files", { value: files, configurable: true });
  fireEvent.change(input);
}

beforeEach(() => {
  mocks.files = [];
  mocks.uploads = [];
  mocks.failNext = false;
});

describe("DocumentsScreen upload", () => {
  it("offers an upload on an empty matter and says what to upload", async () => {
    renderWithIntl(<DocumentsScreen matterId="m1" />);
    const button = await screen.findByRole("button", { name: /Upload documents/ });
    expect(button.className).toContain("bg-primary-bg");
    expect(screen.getByText("No documents yet. Upload the evidence this matter needs.")).toBeTruthy();
    expect(screen.getByText(/Synthetic documents only/)).toBeTruthy();
  });

  it("uploads the chosen files, then lists them as waiting to be processed", async () => {
    renderWithIntl(<DocumentsScreen matterId="m1" />);
    await screen.findByRole("button", { name: /Upload documents/ });
    choose([pdf("synthetic-nic.pdf"), pdf("synthetic-deed.pdf")]);
    expect(await screen.findByText("2 files added. Process them to read their contents.")).toBeTruthy();
    expect(mocks.uploads).toEqual(["synthetic-nic.pdf", "synthetic-deed.pdf"]);
    expect(await screen.findByText("2 files waiting to be processed")).toBeTruthy();
    expect(screen.getByText("synthetic-deed.pdf")).toBeTruthy();
    // With files waiting, processing is the next step, so upload steps back to secondary.
    expect(screen.getByRole("button", { name: /Upload documents/ }).className).not.toContain("bg-primary-bg");
  });

  it("says when a file could not be uploaded, and still keeps the ones that did", async () => {
    renderWithIntl(<DocumentsScreen matterId="m1" />);
    await screen.findByRole("button", { name: /Upload documents/ });
    mocks.failNext = true;
    choose([pdf("broken.pdf"), pdf("synthetic-plan.pdf")]);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("1 file could not be uploaded.");
    await waitFor(() => expect(screen.getByText("synthetic-plan.pdf")).toBeTruthy());
  });
});
