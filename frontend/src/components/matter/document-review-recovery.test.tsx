// @vitest-environment happy-dom
import { webcrypto } from "node:crypto";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import en from "@/lib/i18n/messages/en.json";
import si from "@/lib/i18n/messages/si.json";
import { DocumentProcessingReviewScreen } from "./document-processing-review-screen";
import { FactEvidence } from "./fact-evidence";
import type {
  ApiDetectedDocument,
  ApiFactEvidence,
  ApiSourceFile,
} from "@/types/rta";
const token = async () => "synthetic-token";
vi.mock("@/lib/api/use-token-provider", () => ({
  useTokenProvider: () => token,
}));
vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));
vi.mock("./review-next-step", () => ({ ReviewNextStep: () => null }));
const sources = ["a", "b"].map((suffix) => ({
  id: `synthetic-${suffix}`,
  matterId: "synthetic-matter",
  originalFilename: `Synthetic ${suffix.toUpperCase()}.pdf`,
  state: "PROCESSED",
  sha256: suffix.repeat(64),
  version: 1,
  pageCount: 2,
})) as ApiSourceFile[];
const fragment = (sourceFileId: string) => ({
  id: sourceFileId,
  sourceFileId,
  pageStart: 1,
  pageEnd: 1,
  orderInDocument: 0,
});
let document: ApiDetectedDocument;
let logical: boolean;
let calls: { path: string; init: RequestInit; body: Record<string, unknown> }[];
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://synthetic.test");
  vi.stubGlobal("crypto", webcrypto);
  sessionStorage.clear();
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:synthetic");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  logical = false;
  document = {
    id: "synthetic-doc",
    matterId: "synthetic-matter",
    version: 2,
    interpretationGeneration: 2,
    classId: "rta.doc.nic",
    classStatus: "LAWYER_CONFIRMED",
    boundaryStatus: "CONFIRMED",
    extractionState: "unsupported",
    fragments: [fragment("synthetic-b")],
  } as ApiDetectedDocument;
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const path = String(input).replace("http://synthetic.test", "");
      const body = init.body ? JSON.parse(String(init.body)) : {};
      calls.push({ path, init, body });
      if (path.endsWith("/me")) return response({ id: "synthetic-lawyer" });
      if (path.includes("/review"))
        return logical
          ? response({
              id: "review",
              matterId: document.matterId,
              detectedDocumentId: document.id,
              interpretationGeneration:
                document.extractionState === "current" ? 2 : 1,
              current: document.extractionState === "current",
              typeId: "nic",
              pages: sources.map((source, index) => ({
                id: `page-${index}`,
                sourceFileId: source.id,
                pageNo: 1,
                correctedWidth: 100,
                correctedHeight: 100,
                imageUrl: `/api/v1/processing-pages/page-${index}/image`,
                ocrUrl: `/api/v1/processing-pages/page-${index}/ocr`,
                qualityStatus: "normal",
                rotationStatus: "not_required",
                classificationConfidence: 0.9,
              })),
              candidates: [],
            })
          : response(
              {
                error: {
                  code: "document_review_not_found",
                  message: "Synthetic no processed interpretation",
                },
              },
              404,
            );
      if (path.endsWith("/refresh-extraction")) {
        logical = true;
        document = { ...document, version: 3, extractionState: "current" };
        return response(document);
      }
      if (path.endsWith("/detected-documents/synthetic-doc"))
        return response(document);
      if (path.endsWith("/document-inbox"))
        return response({
          matterId: document.matterId,
          documents: [document],
          sourceFiles: sources,
          page: { hasMore: false, nextCursor: null },
          coverage: {},
        });
      if (path.endsWith("/interpretations"))
        return response({
          snapshots: [],
          refreshRuns: [],
          currentGeneration: 2,
        });
      if (path.includes("document-classes")) return response({ classes: [] });
      if (path.endsWith("/content"))
        return new Response(new Blob(["SYNTHETIC PDF"], { type: "image/png" }));
      if (path.endsWith("/image"))
        return new Response(
          new Blob(["SYNTHETIC IMAGE"], { type: "image/webp" }),
        );
      if (path.endsWith("/ocr")) return response({ elements: [] });
      const source = sources.find((item) =>
        path.endsWith(`/source-files/${item.id}`),
      );
      if (source) return response(source);
      if (path.includes("fact-types"))
        return response({
          factTypes: [
            {
              id: "rta.party.holder_name_en",
              labelKey: "rta.fact.holder_name_en",
              fieldKey: "holderNameEn",
              subject: "PARTY",
              valueKind: "TEXT",
              critical: false,
            },
          ],
          versions: { rulePack: "1" },
        });
      if (path.includes("/facts") && init.method === "POST")
        return response({ id: "synthetic-fact", matterId: document.matterId });
      return response({
        items: path.includes("/source-files") ? sources : [],
        page: { hasMore: false, nextCursor: null, limit: 50 },
      });
    }),
  );
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

it.each(["unsupported", "failed"] as const)(
  "connects the actual no-logical %s route to generation-pinned manual entry and originals",
  async (state) => {
    document.extractionState = state;
    renderWithIntl(
      <DocumentProcessingReviewScreen
        matterId={document.matterId}
        documentId={document.id}
      />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Add information" }),
    );
    fireEvent.change(await screen.findByLabelText(en.factRegister.factType), {
      target: { value: "rta.party.holder_name_en" },
    });
    fireEvent.change(screen.getByLabelText(en.factRegister.manualValue), {
      target: { value: "SYNTHETIC ENTRY" },
    });
    fireEvent.change(screen.getByLabelText(en.factRegister.evidenceSource), {
      target: { value: "synthetic-b" },
    });
    expect(
      screen.getByText(
        en.documentOperations.evidenceGeneration.replace("{generation}", "2"),
      ),
    ).toBeTruthy();
    expect(
      await screen.findByRole("img", { name: /Uploaded document/ }),
    ).toBeTruthy();
  },
);

it("transitions from the no-logical fallback to the first successful refresh without reloading", async () => {
  renderWithIntl(
    <DocumentProcessingReviewScreen
      matterId={document.matterId}
      documentId={document.id}
    />,
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "Refresh extraction" }),
  );
  expect(
    await screen.findByText("Viewing current interpretation 2"),
  ).toBeTruthy();
  expect(
    await screen.findByRole("button", { name: "Synthetic B.pdf · Page 1" }),
  ).toBeTruthy();
});

it.each(["en", "si"] as const)(
  "attributes historical pages from two originals and exposes the current original after failed refresh (%s)",
  async (locale) => {
    logical = true;
    document.extractionState = "failed";
    const messages = locale === "en" ? en : si;
    renderWithIntl(
      <DocumentProcessingReviewScreen
        matterId={document.matterId}
        documentId={document.id}
      />,
      locale,
    );
    expect(
      await screen.findByText(
        messages.documentOperations.historicalView.replace("{generation}", "1"),
      ),
    ).toBeTruthy();
    const pageLabel = messages.documentProcessingReview.page.replace(
      "{page}",
      "1",
    );
    fireEvent.click(
      await screen.findByRole("button", {
        name: `Synthetic B.pdf · ${pageLabel}`,
      }),
    );
    await waitFor(() =>
      expect(calls.some((call) => call.path.endsWith("page-1/image"))).toBe(
        true,
      ),
    );
    expect(
      screen.getByRole("button", { name: `Synthetic A.pdf · ${pageLabel}` }),
    ).toBeTruthy();
    fireEvent.click(
      screen.getByText(messages.documentOperations.currentOriginals),
    );
    await waitFor(() =>
      expect(
        calls.some((call) => call.path.endsWith("synthetic-b/content")),
      ).toBe(true),
    );
    expect(
      calls.some((call) => call.path.endsWith("synthetic-a/content")),
    ).toBe(false);
  },
);

it("offers the readable original instead of a dead processed-page action for manual unsupported evidence", async () => {
  const evidence = {
    id: "evidence",
    sourceFileId: "synthetic-b",
    detectedDocumentId: document.id,
    interpretationGeneration: 2,
    pageNumber: 1,
    precision: "page",
    extractionRunId: null,
    candidateId: null,
    pageText: null,
  } as ApiFactEvidence;
  renderWithIntl(
    <FactEvidence
      matterId={document.matterId}
      evidence={evidence}
      sources={sources}
      getToken={token}
    />,
  );
  expect(
    screen.queryByRole("button", { name: en.factRegister.openPage }),
  ).toBeNull();
  expect(screen.getByText(en.documentOperations.manualOriginal)).toBeTruthy();
  fireEvent.click(
    screen.getByRole("button", { name: en.factRegister.openOriginal }),
  );
  expect(
    await screen.findByRole("link", {
      name: en.factRegister.viewLoadedOriginal,
    }),
  ).toBeTruthy();
});
