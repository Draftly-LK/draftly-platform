// @vitest-environment happy-dom
import { screen, fireEvent, act } from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import { DocumentProcessingReviewScreen } from "./document-processing-review-screen";
import type * as FactRegisterModule from "./fact-register";
const token = async () => "synthetic-token";
const simulation = vi.hoisted(() => ({ enabled: false }));
vi.mock("./fact-register", async (importOriginal) => {
  const actual = await importOriginal<typeof FactRegisterModule>();
  return {
    FactRegister: (props: Parameters<typeof actual.FactRegister>[0]) =>
      simulation.enabled ? (
        <button onClick={props.onDecision}>SYNTHETIC complete decision</button>
      ) : (
        <actual.FactRegister {...props} />
      ),
  };
});
vi.mock("@/lib/api/use-token-provider", () => ({
  useTokenProvider: () => token,
}));
vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));
vi.mock("./document-decisions", async () => {
  const { useEffect } = await import("react");
  return {
    DocumentDecisions: ({
      onChange,
    }: {
      onChange: (document: object) => void;
    }) => {
      useEffect(() => {
        if (simulation.enabled)
          onChange({ id: "synthetic-document", fragments: [] });
      }, [onChange]);
      return null;
    },
    isDocumentDecided: () => simulation.enabled,
  };
});
vi.mock("./review-next-step", () => ({
  ReviewNextStep: ({ done }: { done: boolean }) =>
    simulation.enabled ? (
      <p>{done ? "SYNTHETIC DONE" : "SYNTHETIC PENDING"}</p>
    ) : null,
}));
beforeEach(() => {
  simulation.enabled = false;
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://synthetic.test");
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (input: RequestInfo | URL) =>
        new Response(
          JSON.stringify(
            String(input).endsWith("/review")
              ? {
                  id: "review",
                  matterId: "synthetic-matter",
                  detectedDocumentId: "synthetic-document",
                  typeId: "nic",
                  suggestedName: null,
                  pages: [],
                  candidates: [
                    {
                      id: "candidate",
                      key: "holderNameEn",
                      candidateValue: "SYNTHETIC HOLDER",
                      editedValue: null,
                      pageNo: 1,
                      modelReportedConfidence: 0.8,
                      reviewState: "unverified",
                      version: 1,
                    },
                  ],
                }
              : String(input).includes("fact-types")
                ? { factTypes: [], versions: { rulePack: "1" } }
                : {
                    items: [],
                    page: { hasMore: false, nextCursor: null, limit: 50 },
                  },
          ),
          { headers: { "Content-Type": "application/json" } },
        ),
    ),
  );
});

it("keeps the newest document review projection when earlier refreshes arrive late", async () => {
  simulation.enabled = true;
  let reads = 0;
  let resolveOld: ((response: Response) => void) | undefined;
  const review = {
    id: "review",
    matterId: "synthetic-matter",
    detectedDocumentId: "synthetic-document",
    typeId: "nic",
    pages: [],
    candidates: [{ reviewState: "unverified" }],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      reads++;
      if (reads === 2)
        return new Promise<Response>((resolve) => {
          resolveOld = resolve;
        });
      return new Response(
        JSON.stringify(reads === 3 ? { ...review, candidates: [] } : review),
      );
    }),
  );
  renderWithIntl(
    <DocumentProcessingReviewScreen
      matterId="synthetic-matter"
      documentId="synthetic-document"
    />,
  );
  const trigger = await screen.findByRole("button", {
    name: "SYNTHETIC complete decision",
  });
  fireEvent.click(trigger);
  fireEvent.click(trigger);
  await screen.findByText("SYNTHETIC DONE");
  await act(async () => {
    resolveOld!(new Response(JSON.stringify(review)));
  });
  expect(screen.getByText("SYNTHETIC DONE")).toBeTruthy();
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
it("connects document field review to canonical scope/decision controls", async () => {
  renderWithIntl(
    <DocumentProcessingReviewScreen
      matterId="synthetic-matter"
      documentId="synthetic-document"
    />,
  );
  expect(
    await screen.findByText(
      "Candidates and reviewed facts are available before a form is created.",
    ),
  ).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Approve all/ })).toBeNull();
  expect(screen.getByRole("button", { name: "Add information" })).toBeTruthy();
});

it("keeps the readable page when optional OCR is unavailable", async () => {
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:synthetic-page");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  const original = global.fetch;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const path = String(input);
      if (path.endsWith("/image"))
        return new Response(
          new Blob(["Synthetic page"], { type: "image/webp" }),
        );
      if (path.endsWith("/ocr"))
        return new Response(
          JSON.stringify({
            error: {
              code: "synthetic_ocr_missing",
              message: "Synthetic optional OCR unavailable",
            },
          }),
          { status: 503 },
        );
      if (path.endsWith("/review"))
        return new Response(
          JSON.stringify({
            id: "review",
            matterId: "synthetic-matter",
            detectedDocumentId: "synthetic-document",
            typeId: "nic",
            pages: [
              {
                id: "page",
                pageNo: 1,
                correctedWidth: 100,
                correctedHeight: 100,
                imageUrl: "/api/v1/processing-pages/page/image",
                ocrUrl: "/api/v1/processing-pages/page/ocr",
                qualityStatus: "normal",
                rotationStatus: "not_required",
                classificationConfidence: 0.9,
              },
            ],
            candidates: [],
          }),
          { headers: { "Content-Type": "application/json" } },
        );
      return original(input, init);
    }),
  );
  renderWithIntl(
    <DocumentProcessingReviewScreen
      matterId="synthetic-matter"
      documentId="synthetic-document"
    />,
  );
  expect(
    await screen.findByRole("img", { name: "Corrected document page 1" }),
  ).toBeTruthy();
  expect(
    await screen.findByText("Stored OCR text is unavailable."),
  ).toBeTruthy();
});
