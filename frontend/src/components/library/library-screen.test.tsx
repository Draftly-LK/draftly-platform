// @vitest-environment happy-dom
import { fireEvent, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import { casePage, similarCases, syntheticCase } from "@/test/case-fixtures";

vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/components/shell/page-header", () => ({
  PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}));
const token = async () => "synthetic-token";
vi.mock("@/lib/api/use-token-provider", () => ({
  useTokenProvider: () => token,
}));
import { LibraryScreen } from "./library-screen";
import { CaseCatalogueFlow, CaseReaderFlow, CaseSearchFlow } from "./case-law";

describe("case law entry", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });
  it("opens case catalogue independently from statutory sources", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.test");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        Response.json(
          url.includes("/cases")
            ? {
                corpusVersion: "synthetic-v1",
                coverage: {
                  catalogueRecords: 3,
                  retrievalRecords: 2,
                  readerOverlapRecords: 1,
                  collections: { LKCA: 2, LKSC: 1 },
                  minYear: 1990,
                  maxYear: 2000,
                  retrievalScope: "conveyancing-only",
                },
                items: [],
                page: { hasMore: false, nextCursor: null, limit: 25 },
              }
            : { items: [], total: 0 },
        ),
      ),
    );
    renderWithIntl(<LibraryScreen />);
    fireEvent.click(screen.getByRole("button", { name: "Case law" }));
    await waitFor(() =>
      expect(screen.getByText(/3 catalogue records/)).toBeTruthy(),
    );
    expect(
      screen.getByRole("textbox", { name: "Name or citation" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("textbox", { name: "Describe the facts" }),
    ).toBeTruthy();
  });

  async function openCases(fetch: typeof globalThis.fetch) {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.test");
    vi.stubGlobal("fetch", fetch);
    renderWithIntl(<LibraryScreen />);
    fireEvent.click(screen.getByRole("button", { name: "Case law" }));
    await screen.findByRole("link", { name: syntheticCase.title });
  }
  const response = (value: unknown) => Response.json(value);

  it("preserves a previous cursor stack and resets it when filters change", async () => {
    const urls: string[] = [];
    await openCases(async (input) => {
      const url = String(input);
      urls.push(url);
      return response(
        url.endsWith("/library")
          ? { items: [] }
          : url.includes("cursor=")
            ? {
                ...casePage,
                items: [
                  {
                    ...syntheticCase,
                    id: "commonlii-SYNTHETIC-2",
                    title: "Synthetic Second Case",
                  },
                ],
                page: { ...casePage.page, hasMore: false, nextCursor: null },
              }
            : casePage,
      );
    });
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText("Synthetic Second Case");
    expect(urls.at(-1)).toContain("cursor=signed-page-2");
    fireEvent.click(screen.getByRole("button", { name: "Previous page" }));
    await screen.findByRole("link", { name: syntheticCase.title });
    expect(urls.at(-1)).not.toContain("cursor=");
    fireEvent.change(
      screen.getByRole("combobox", { name: "Court collection" }),
      { target: { value: "LKSC" } },
    );
    fireEvent.change(screen.getByRole("spinbutton", { name: "Year" }), {
      target: { value: "2000" },
    });
    fireEvent.change(
      screen.getByRole("textbox", { name: "Name or citation" }),
      { target: { value: "Synthetic" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    await waitFor(() => expect(urls.at(-1)).toContain("year=2000"));
    expect(urls.at(-1)).toContain("collection=LKSC");
    expect(urls.at(-1)).not.toContain("cursor=");
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: "Previous page" })
        .disabled,
    ).toBe(true);
  });

  it("moves keyboard focus from the catalogue jump link to fact-pattern search", async () => {
    await openCases(async (input) =>
      response(String(input).endsWith("/library") ? { items: [] } : casePage),
    );
    const jump = screen.getByRole("link", { name: "Search a fact pattern" });
    jump.focus();
    fireEvent.click(jump);
    const destination = document.getElementById("case-search");
    expect(destination).not.toBeNull();
    expect(document.activeElement).toBe(destination);
    expect(destination?.getAttribute("tabindex")).toBe("-1");
  });

  it("offers restart for a stale cursor instead of reporting an empty catalogue", async () => {
    await openCases(async (input) =>
      String(input).includes("cursor=")
        ? Response.json(
            {
              error: {
                code: "invalid_cursor",
                message: "Synthetic stale cursor",
              },
            },
            { status: 400 },
          )
        : response(
            String(input).endsWith("/library") ? { items: [] } : casePage,
          ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByRole("button", { name: "Restart browse" });
    expect(screen.queryByText("No judgments match these filters.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Restart browse" }));
    await screen.findByRole("link", { name: syntheticCase.title });
  });

  it("retries the same logical search with one key and changes key for new facts", async () => {
    const requests: { query: string; key: string }[] = [];
    await openCases(async (input, init) => {
      if (!String(input).includes("/search"))
        return response(
          String(input).endsWith("/library") ? { items: [] } : casePage,
        );
      requests.push({
        query: JSON.parse(String(init?.body)).query,
        key: new Headers(init?.headers).get("Idempotency-Key")!,
      });
      return requests.length === 1
        ? Response.json(
            { error: { code: "case_corpus_unavailable" } },
            { status: 503 },
          )
        : response(similarCases);
    });
    const facts = screen.getByRole("textbox", { name: "Describe the facts" });
    fireEvent.change(facts, { target: { value: "Synthetic boundary facts" } });
    fireEvent.click(screen.getByRole("button", { name: "Find similar cases" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Retry search" }),
    );
    await screen.findByText(
      "Synthetic evidence excerpt. Preserved second line.",
    );
    expect(requests[0]!.key).toBe(requests[1]!.key);
    expect(screen.getByText("Semantic matching is disabled.")).toBeTruthy();
    expect(screen.getByText("Word match")).toBeTruthy();
    expect(screen.getByText("Related legal terms")).toBeTruthy();
    fireEvent.change(facts, { target: { value: "Synthetic different facts" } });
    fireEvent.click(screen.getByRole("button", { name: "Find similar cases" }));
    await waitFor(() => expect(requests).toHaveLength(3));
    expect(requests[2]!.key).not.toBe(requests[1]!.key);
    expect(requests[2]!.query).toBe("Synthetic different facts");
  });

  it("shows explicit no-results and outside-catalogue source links", async () => {
    let search = 0;
    await openCases(async (input) => {
      if (!String(input).includes("/search"))
        return response(
          String(input).endsWith("/library") ? { items: [] } : casePage,
        );
      search++;
      return response(
        search === 1
          ? { ...similarCases, outcome: "no_similar_cases", items: [] }
          : {
              ...similarCases,
              denseStatus: "enabled-status-unknown",
              degradedChannels: [],
              items: [
                {
                  ...similarCases.items[0],
                  case: null,
                  readerAvailable: false,
                  title: "Synthetic External Case",
                },
              ],
            },
      );
    });
    const facts = screen.getByRole("textbox", { name: "Describe the facts" });
    fireEvent.change(facts, { target: { value: "Synthetic empty pattern" } });
    fireEvent.click(screen.getByRole("button", { name: "Find similar cases" }));
    await screen.findByText(
      "No similar cases found. Try describing the facts differently.",
    );
    fireEvent.change(facts, {
      target: { value: "Synthetic external pattern" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Find similar cases" }));
    const link = await screen.findByRole("link", {
      name: "Synthetic External Case",
    });
    expect(link.getAttribute("href")).toBe(
      "https://example.test/synthetic-case",
    );
    expect(
      screen.getByText(
        "Semantic matching is enabled; its availability could not be confirmed.",
      ),
    ).toBeTruthy();
  });

  async function reader(item: typeof syntheticCase) {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.test");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => response({ ...casePage, item })),
    );
    return renderWithIntl(<CaseReaderFlow getToken={token} caseId={item.id} />);
  }

  it("shows collection separately from deciding court and fails text display closed", async () => {
    await reader({ ...syntheticCase, text: "SHOULD NOT DISPLAY" });
    await screen.findByText(
      "Full text awaits display approval. Use the source link to inspect the judgment.",
    );
    expect(screen.queryByText("SHOULD NOT DISPLAY")).toBeNull();
    expect(
      screen.getByText(/Deciding court: Synthetic District Court/),
    ).toBeTruthy();
    expect(screen.getByText(/Court of Appeal collection/)).toBeTruthy();
    expect(screen.queryByText(/unverified/i)).toBeNull();
    expect(
      screen.queryByText("Encoding errors may affect this extraction."),
    ).toBeNull();
    expect(
      screen
        .getByRole("link", { name: "Back to case law" })
        .getAttribute("href"),
    ).toBe("/library?tab=cases");
  });

  it("renders approved text as plain whitespace-preserving content", async () => {
    const { container } = await reader({
      ...syntheticCase,
      displayPolicy: "full-text",
      displayApprovalReference: "Synthetic approval",
      text: "<script>synthetic()</script>\n\nSynthetic next paragraph",
    });
    await screen.findByText(/<script>synthetic\(\)<\/script>/);
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("[data-case-text]")?.textContent).toBe(
      "<script>synthetic()</script>\n\nSynthetic next paragraph",
    );
    expect(container.querySelector("[data-case-text]")?.className).toContain(
      "whitespace-pre-wrap",
    );
  });

  it("withholds full-text records that lack a recorded approval reference", async () => {
    await reader({
      ...syntheticCase,
      displayPolicy: "full-text",
      displayApprovalReference: "  ",
      text: "SHOULD NOT DISPLAY",
    });
    await screen.findByText(
      "Full text awaits display approval. Use the source link to inspect the judgment.",
    );
    expect(screen.queryByText("SHOULD NOT DISPLAY")).toBeNull();
  });

  it("separates missing reader records from retryable unavailability", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.test");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({ error: { code: "not_found" } }, { status: 404 }),
      ),
    );
    renderWithIntl(
      <CaseReaderFlow getToken={token} caseId="commonlii-SYNTHETIC-missing" />,
    );
    await screen.findByRole("alert");
    expect(
      screen.getByText("This judgment is not in the catalogue."),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("bounds displayed results and excerpts and labels optional channel unavailability", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.test");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        response({
          ...similarCases,
          denseStatus: "unavailable",
          items: Array.from({ length: 9 }, (_, index) => ({
            ...similarCases.items[0],
            id: `commonlii-SYNTHETIC-${index}`,
            title: `Synthetic Result ${index}`,
            excerpt: "x".repeat(900) + "TRUNCATED",
          })),
        }),
      ),
    );
    renderWithIntl(<CaseSearchFlow getToken={token} />);
    fireEvent.change(
      screen.getByRole("textbox", { name: "Describe the facts" }),
      { target: { value: "Synthetic facts" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Find similar cases" }));
    await screen.findByText("8 similar cases");
    expect(screen.getAllByRole("article")).toHaveLength(8);
    expect(screen.queryByText(/TRUNCATED/)).toBeNull();
    expect(
      screen.getByText(
        "Semantic matching is unavailable. Word and related-term matching remain available.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText(/0\.2/)).toBeNull();
  });

  it("distinguishes quota or feature denial from retryable service failures", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.test");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          { error: { code: "plan_limit_exceeded" } },
          { status: 429 },
        ),
      ),
    );
    renderWithIntl(<CaseSearchFlow getToken={token} />);
    fireEvent.change(
      screen.getByRole("textbox", { name: "Describe the facts" }),
      { target: { value: "Synthetic facts" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Find similar cases" }));
    await screen.findByText(
      "Case search is not available on your current plan or your query allowance has been used.",
    );
    expect(screen.queryByRole("button", { name: "Retry search" })).toBeNull();
  });

  it("localizes catalogue controls and empty state in Sinhala", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.test");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        response({
          ...casePage,
          items: [],
          coverage: { ...casePage.coverage, minYear: null, maxYear: null },
        }),
      ),
    );
    renderWithIntl(<CaseCatalogueFlow getToken={token} />, "si");
    await screen.findByText("මෙම පෙරහන්වලට ගැළපෙන නඩු තීන්දු නොමැත.");
    expect(screen.getByRole("textbox", { name: "නම හෝ උපුටනය" })).toBeTruthy();
    expect(
      screen.getByRole("textbox", { name: "කරුණු විස්තර කරන්න" }),
    ).toBeTruthy();
    expect(screen.getByText(/වසර පරාසය නොමැත/)).toBeTruthy();
  });
});
