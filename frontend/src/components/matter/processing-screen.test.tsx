// @vitest-environment happy-dom
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import type { ApiProcessingRun, ApiSourceFile } from "@/types/rta";

const mocks = vi.hoisted(() => ({
  token: async () => null,
  list: vi.fn(),
  status: vi.fn(),
  source: vi.fn(),
  process: vi.fn(),
}));
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  isApiEnabled: () => true,
}));
vi.mock("@/lib/api/use-token-provider", () => ({
  useTokenProvider: () => mocks.token,
}));
vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("@/lib/api/documents", () => ({
  listSourceFiles: mocks.list,
  getSourceProcessingStatus: mocks.status,
  getSourceFile: mocks.source,
  processSourceFile: mocks.process,
}));
import { ApiError } from "@/lib/api/client";
import { ProcessingScreen } from "./processing-screen";

const source = (overrides: Partial<ApiSourceFile> = {}): ApiSourceFile => ({
  id: "sf-synthetic",
  matterId: "m-synthetic",
  originalFilename: "synthetic-evidence.pdf",
  mediaType: "application/pdf",
  byteLength: 20,
  sha256: "synthetic-hash",
  storageObjectVersion: "synthetic-version",
  uploadActorId: "synthetic-user",
  state: "STORED",
  pageCount: 2,
  detectedLanguages: [],
  retentionClass: "rta.client-evidence",
  failureReason: null,
  failureExplanationKey: null,
  supersededBySourceFileId: null,
  derivedFromSourceFileId: null,
  duplicateOfSourceFileId: null,
  versionRelationship: null,
  detectedDocumentIds: [],
  containsMultipleDocuments: false,
  createdAt: "2026-10-09T00:00:00Z",
  updatedAt: "2026-10-09T00:00:00Z",
  version: 1,
  ...overrides,
});
const run = (
  file: ApiSourceFile,
  overrides: Partial<ApiProcessingRun> = {},
): ApiProcessingRun => ({
  jobId: "run-synthetic",
  state: "failed",
  pollAfterMs: null,
  sourceFileId: file.id,
  provider: "synthetic-unavailable",
  outcome: "PROCESSING_FAILED",
  reasons: ["NOT_CONFIGURED"],
  failureReason: "NOT_CONFIGURED",
  failureExplanationKey: "rta.source_file.failure.not_configured",
  pagesProcessed: 0,
  aiExtractionCalls: 0,
  startedAt: "2026-10-09T00:00:00Z",
  finishedAt: "2026-10-09T00:00:01Z",
  correlationId: "synthetic-correlation",
  sourceFile: file,
  detectedDocuments: [],
  candidateFields: [],
  candidatesWithheld: false,
  ...overrides,
});
const page = (items: ApiSourceFile[], nextCursor: string | null = null) => ({
  items,
  page: { nextCursor, hasMore: nextCursor !== null, limit: 50 },
});
const status = (
  file: ApiSourceFile,
  latestRun: ApiProcessingRun | null = null,
  extra = {},
) => ({
  sourceFile: file,
  latestRun: latestRun
    ? { ...latestRun, pageOutcomes: [], manualReviewRequired: false, ...extra }
    : null,
});

beforeEach(() => {
  vi.resetAllMocks();
  const file = source();
  mocks.list.mockResolvedValue(page([file]));
  mocks.source.mockResolvedValue(file);
  mocks.status.mockResolvedValue(status(file));
});

describe("ProcessingScreen persisted outcomes", () => {
  it("keeps a superseded source distinct from an old successful run", async () => {
    const file = source({
      state: "SUPERSEDED",
      supersededBySourceFileId: "sf-successor",
    });
    mocks.list.mockResolvedValue(page([file]));
    mocks.status.mockResolvedValue(
      status(
        file,
        run(file, {
          state: "succeeded",
          outcome: "PROCESSED",
          reasons: [],
          failureReason: null,
        }),
      ),
    );
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    expect(await screen.findByText("Replaced")).toBeTruthy();
    expect(screen.queryByText("Success")).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Retry processing" }),
    ).toBeNull();
  });
  it("does not treat a failed run with a source ID as success and preserves recovery on refresh", async () => {
    const failed = source({
      state: "PROCESSING_FAILED",
      version: 3,
      failureReason: "NOT_CONFIGURED",
    });
    mocks.process.mockImplementation(async () => {
      mocks.status.mockResolvedValue(status(failed, run(failed)));
      mocks.source.mockResolvedValue(failed);
      mocks.list.mockResolvedValue(page([failed]));
      return run(failed);
    });
    const view = renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    fireEvent.click(await screen.findByRole("button", { name: "Process" }));
    expect(
      await screen.findByText(
        "Processing provider is unavailable.",
        {},
        { timeout: 2500 },
      ),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Retry processing" }),
    ).toBeTruthy();
    expect(screen.queryByText("Success")).toBeNull();
    expect(
      screen.queryByRole("link", { name: /Continue to document inbox/ }),
    ).toBeNull();
    view.unmount();
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    expect(
      await screen.findByText("Processing provider is unavailable."),
    ).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Review documents manually" }),
    ).toBeTruthy();
  });

  it("reads successful terminal state from the persisted run", async () => {
    const file = source({ state: "PROCESSED", version: 3 });
    mocks.list.mockResolvedValue(page([file]));
    mocks.status.mockResolvedValue(
      status(
        file,
        run(file, {
          state: "succeeded",
          outcome: "PROCESSED",
          reasons: [],
          failureReason: null,
          pagesProcessed: 2,
        }),
      ),
    );
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    expect(await screen.findByText("Success")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: /Continue to document inbox/ }),
    ).toBeTruthy();
  });

  it("keeps missing run state unknown even if a source says processed", async () => {
    const file = source({ state: "PROCESSED" });
    mocks.list.mockResolvedValue(page([file]));
    mocks.status.mockResolvedValue(status(file));
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    expect(
      await screen.findByText("Processing outcome is unavailable."),
    ).toBeTruthy();
    expect(
      screen.queryByRole("link", { name: /Continue to document inbox/ }),
    ).toBeNull();
  });

  it("disables retry after a status read fails until refresh restores the recorded failure", async () => {
    const failed = source({
      state: "PROCESSING_FAILED",
      failureReason: "NOT_CONFIGURED",
    });
    mocks.list.mockResolvedValue(page([failed]));
    mocks.status.mockRejectedValue(new Error("synthetic status outage"));
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    const retry = await screen.findByRole("button", {
      name: "Retry processing",
    });
    expect(retry.hasAttribute("disabled")).toBe(true);
    fireEvent.click(retry);
    expect(mocks.source).not.toHaveBeenCalled();
    expect(mocks.process).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("link", { name: /Continue to document inbox/ }),
    ).toBeNull();

    mocks.status.mockResolvedValue(status(failed, run(failed)));
    fireEvent.click(
      screen.getByRole("button", { name: "Refresh processing status" }),
    );
    await waitFor(() =>
      expect(
        screen
          .getByRole("button", { name: "Retry processing" })
          .hasAttribute("disabled"),
      ).toBe(false),
    );
    expect(mocks.status).toHaveBeenCalledTimes(2);
    expect(
      screen.queryByRole("link", { name: /Continue to document inbox/ }),
    ).toBeNull();
  });

  it("withholds successful continuation after a status read fails until refresh confirms success", async () => {
    const done = source({ state: "PROCESSED" });
    mocks.list.mockResolvedValue(page([done]));
    mocks.status.mockRejectedValue(new Error("synthetic status outage"));
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    expect(
      await screen.findByText("Processing outcome is unavailable."),
    ).toBeTruthy();
    expect(screen.queryByText("Success")).toBeNull();
    expect(
      screen.queryByRole("link", { name: /Continue to document inbox/ }),
    ).toBeNull();

    mocks.status.mockResolvedValue(
      status(
        done,
        run(done, {
          state: "succeeded",
          outcome: "PROCESSED",
          failureReason: null,
          reasons: [],
        }),
      ),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Refresh processing status" }),
    );
    expect(await screen.findByText("Success")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: /Continue to document inbox/ }),
    ).toBeTruthy();
    expect(mocks.status).toHaveBeenCalledTimes(2);
  });

  it("shows retained failed pages and manual review without claiming full success", async () => {
    const file = source({ state: "PROCESSED" });
    mocks.list.mockResolvedValue(page([file]));
    mocks.status.mockResolvedValue(
      status(
        file,
        run(file, {
          state: "succeeded",
          outcome: "PROCESSED",
          failureReason: null,
          reasons: [],
        }),
        {
          manualReviewRequired: true,
          pageOutcomes: [
            {
              pageNo: 1,
              qualityStatus: "normal",
              rotationStatus: "not_required",
            },
            {
              pageNo: 2,
              qualityStatus: "ocr_failed",
              rotationStatus: "rotation_uncertain",
            },
          ],
        },
      ),
    );
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    expect(
      await screen.findByText("Processing finished; manual review required."),
    ).toBeTruthy();
    expect(
      screen.getByText("Page 2: OCR failed; review the original page."),
    ).toBeTruthy();
    expect(screen.getByText("Page 2: rotation is uncertain.")).toBeTruthy();
    expect(screen.queryByText("Success")).toBeNull();
  });

  it("refreshes the source version before retry and accepts the new persisted outcome", async () => {
    const failed = source({ state: "PROCESSING_FAILED", version: 3 });
    const fresh = source({ state: "PROCESSING_FAILED", version: 7 });
    const succeeded = source({ state: "PROCESSED", version: 9 });
    mocks.list.mockResolvedValue(page([failed]));
    mocks.status.mockResolvedValue(status(failed, run(failed)));
    mocks.source.mockResolvedValue(fresh);
    mocks.process.mockImplementation(async () => {
      mocks.status.mockResolvedValue(
        status(
          succeeded,
          run(succeeded, {
            state: "succeeded",
            outcome: "PROCESSED",
            failureReason: null,
            reasons: [],
          }),
        ),
      );
      return run(succeeded);
    });
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Retry processing" }),
    );
    expect(await screen.findByText("Success")).toBeTruthy();
    expect(mocks.process).toHaveBeenCalledWith(mocks.token, failed.id, 7);
  });

  it("reports a concurrent stale-version rejection without automatically retrying the mutation", async () => {
    mocks.process.mockRejectedValue(
      new ApiError(412, "source_file_stale", "stale", "synthetic", {}),
    );
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    fireEvent.click(await screen.findByRole("button", { name: "Process" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(
      screen.getByText(
        "The file changed. Review the refreshed state before retrying.",
      ),
    ).toBeTruthy();
    expect(mocks.process).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Success")).toBeNull();
  });

  it("ignores an old matter's delayed ineligible-source status after switching matters", async () => {
    const old = source();
    const oldDone = source({ state: "PROCESSED" });
    const next = source({
      id: "sf-next-matter",
      matterId: "m-next-synthetic",
      originalFilename: "synthetic-next-matter.pdf",
      state: "PROCESSED",
    });
    const succeeded = (file: ApiSourceFile) =>
      status(
        file,
        run(file, {
          state: "succeeded",
          outcome: "PROCESSED",
          failureReason: null,
          reasons: [],
        }),
      );
    let finishOldStatus!: (value: ReturnType<typeof status>) => void;
    const oldStatus = new Promise<ReturnType<typeof status>>((resolve) => {
      finishOldStatus = resolve;
    });
    mocks.list.mockImplementation(async (_token, matterId) =>
      page([matterId === old.matterId ? old : next]),
    );
    mocks.status
      .mockResolvedValueOnce(status(old))
      .mockImplementation(async (_token, id) =>
        id === old.id ? oldStatus : succeeded(next),
      );
    mocks.source.mockResolvedValue(oldDone);
    function MatterSwitch() {
      const [matterId, setMatterId] = useState(old.matterId);
      return (
        <>
          <button onClick={() => setMatterId(next.matterId)}>
            Switch synthetic matter
          </button>
          <ProcessingScreen matterId={matterId} />
        </>
      );
    }
    renderWithIntl(<MatterSwitch />);
    fireEvent.click(await screen.findByRole("button", { name: "Process" }));
    await waitFor(() => expect(mocks.status).toHaveBeenCalledTimes(2));
    fireEvent.click(
      screen.getByRole("button", { name: "Switch synthetic matter" }),
    );
    expect(await screen.findByText(next.originalFilename)).toBeTruthy();
    expect(screen.getByText("Success")).toBeTruthy();

    await act(async () => finishOldStatus(succeeded(oldDone)));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(
      screen
        .getByRole("link", { name: /Continue to document inbox/ })
        .getAttribute("href"),
    ).toBe(`/matters/${next.matterId}/documents`);
    expect(mocks.process).not.toHaveBeenCalled();
  });

  it("loads later source-file pages before offering completion", async () => {
    const done = source({ state: "PROCESSED" });
    const waiting = source({
      id: "sf-later",
      originalFilename: "synthetic-later.pdf",
    });
    mocks.list.mockImplementation(async (_token, _matter, params) =>
      params?.cursor ? page([waiting]) : page([done], "next-synthetic"),
    );
    mocks.status.mockImplementation(async (_token, id) =>
      id === waiting.id
        ? status(waiting)
        : status(
            done,
            run(done, {
              state: "succeeded",
              outcome: "PROCESSED",
              reasons: [],
              failureReason: null,
            }),
          ),
    );
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    expect(await screen.findByText("synthetic-later.pdf")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Process" })).toBeTruthy();
    expect(
      screen.queryByRole("link", { name: /Continue to document inbox/ }),
    ).toBeNull();
  });

  it("shows a recoverable error for a repeated pagination cursor", async () => {
    mocks.list.mockResolvedValue(page([source()], "repeated"));
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(
      screen.getByText(
        "The complete file list could not be loaded. Refresh processing status.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Refresh processing status" }),
    ).toBeTruthy();
    expect(
      screen.queryByRole("link", { name: /Continue to document inbox/ }),
    ).toBeNull();
  });

  it("distinguishes an empty list from a failed request", async () => {
    mocks.list.mockResolvedValue(page([]));
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    expect(await screen.findByText("No documents uploaded yet.")).toBeTruthy();
    expect(
      screen.queryByRole("link", { name: /Continue to document inbox/ }),
    ).toBeNull();
  });

  it("shows list errors instead of hiding them behind the empty state", async () => {
    mocks.list.mockRejectedValue(new Error("synthetic outage"));
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(
      screen.getByText("Something went wrong. Please try again."),
    ).toBeTruthy();
    expect(screen.queryByText("synthetic outage")).toBeNull();
    expect(screen.queryByText("No documents uploaded yet.")).toBeNull();
    mocks.list.mockResolvedValue(page([source()]));
    fireEvent.click(
      screen.getByRole("button", { name: "Refresh processing status" }),
    );
    expect(await screen.findByRole("button", { name: "Process" })).toBeTruthy();
  });

  it("locks mutation controls while processing rather than showing continuation", async () => {
    let finish: (() => void) | undefined;
    mocks.process.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve;
        }),
    );
    renderWithIntl(<ProcessingScreen matterId="m-synthetic" />);
    fireEvent.click(await screen.findByRole("button", { name: "Process" }));
    await waitFor(() =>
      expect(
        screen
          .getByRole("button", { name: "Processing…" })
          .hasAttribute("disabled"),
      ).toBe(true),
    );
    expect(
      screen.queryByRole("link", { name: /Continue to document inbox/ }),
    ).toBeNull();
    finish?.();
  });
});
