// @vitest-environment happy-dom
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";

vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/components/shell/page-header", () => ({
  PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}));
const token = async () => "synthetic-token";
vi.mock("@/lib/api/use-token-provider", () => ({ useTokenProvider: () => token }));
import { ResearchScreen } from "./research-screen";

const conversation = {
  id: "rconv-1",
  title: "Synthetic question",
  scope: { type: "library" },
  activeBranchId: "rbranch-1",
  createdAt: "2026-10-06T03:00:00Z",
  updatedAt: "2026-10-06T03:00:00Z",
};
const statuteCitation = {
  id: "rcite-1",
  sourceId: "SRC011",
  authorityId: "SRC011:s39",
  passage: "A disposition otherwise effected shall be void.",
  page: 13,
  verified: true,
  authorityKind: "statute",
  title: "Registration of Title Act",
  reference: "Section 39",
  sourceUrl: null,
};
const caseCitation = {
  id: "rcite-2",
  sourceId: "case-law",
  authorityId: "commonlii-LKCA-1999-1",
  passage: "Later-acquired title inures to the buyer.",
  page: 0,
  verified: false,
  authorityKind: "case",
  title: "Synthetic Vendor v. Synthetic Purchaser",
  reference: "[1999] LKCA 1",
  sourceUrl: "https://example.test/cases/LKCA/1999/1.html",
};
const userMessage = {
  id: "rmsg-1",
  conversationId: "rconv-1",
  branchId: "rbranch-1",
  role: "user",
  content: "Who holds title after a resale?",
  citations: [],
  claims: [],
  createdAt: "2026-10-06T03:00:00Z",
};

function answer(overrides: Record<string, unknown>) {
  return {
    id: "rmsg-2",
    conversationId: "rconv-1",
    branchId: "rbranch-1",
    parentMessageId: "rmsg-1",
    role: "assistant",
    answerId: "rans-1",
    createdAt: "2026-10-06T03:00:01Z",
    ...overrides,
  };
}

function stubApi(messages: unknown[]) {
  const posts: Array<{ url: string; body: unknown }> = [];
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.test");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        posts.push({ url, body: JSON.parse(String(init.body)) });
        return Response.json({ jobId: "rjob-1", state: "succeeded", pollAfterMs: 1500 }, { status: 202 });
      }
      if (url.endsWith("/messages")) return Response.json({ items: messages });
      return Response.json({ items: [conversation] });
    }),
  );
  return posts;
}

describe("research source scope", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("defaults to statutes and sends the chosen source with the question", async () => {
    const posts = stubApi([]);
    renderWithIntl(<ResearchScreen />);
    const statutes = await screen.findByRole("button", { name: "Statutes & amendments" });
    await waitFor(() => expect((statutes as HTMLButtonElement).disabled).toBe(false));
    expect(statutes.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("Search the approved statutory corpus.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Case law" }));
    expect(screen.getByText("Search reported Sri Lankan case law.")).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("Ask a legal research question…"), {
      target: { value: "Who holds title after a resale?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]?.url).toBe("https://api.test/api/v1/research/conversations/rconv-1/messages");
    expect(posts[0]?.body).toMatchObject({ content: "Who holds title after a resale?", sources: "cases" });
  });

  it("sends statutes when the source is left alone", async () => {
    const posts = stubApi([]);
    renderWithIntl(<ResearchScreen />);
    await waitFor(() =>
      expect((screen.getByPlaceholderText("Ask a legal research question…") as HTMLTextAreaElement).disabled).toBe(false),
    );
    fireEvent.change(screen.getByPlaceholderText("Ask a legal research question…"), { target: { value: "Q?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]?.body).toMatchObject({ sources: "statutes" });
  });
});

describe("research answer sources", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("groups statutes and case law in one answer, listing each case once", async () => {
    stubApi([
      userMessage,
      answer({
        content: "Statute claim.\n\nCase claim.",
        citations: [statuteCitation, caseCitation, { ...caseCitation, id: "rcite-3" }],
        claims: [
          { text: "Statute claim.", citationIds: ["SRC011:s39"] },
          { text: "Case claim.", citationIds: ["commonlii-LKCA-1999-1"] },
        ],
      }),
    ]);
    renderWithIntl(<ResearchScreen />);
    const sources = (await screen.findByText("Sources used")).parentElement as HTMLElement;

    expect(within(sources).getByText("Registration of Title Act — Section 39")).toBeTruthy();
    expect(within(sources).getByText("Synthetic Vendor v. Synthetic Purchaser")).toBeTruthy();
    // The same case cited twice is listed once.
    expect(within(sources).getAllByText("Synthetic Vendor v. Synthetic Purchaser")).toHaveLength(1);
    const link = within(sources).getByRole("link", { name: "Open source" });
    expect(link.getAttribute("href")).toBe("https://example.test/cases/LKCA/1999/1.html");
    expect(screen.getByText("Statute claim.").textContent).toContain("Statute");
    expect(screen.getByText("Case claim.").textContent).toContain("Case law");
    expect(screen.queryByText(/unverified|attorney review/i)).toBeNull();
  });

  it("only links a case to a web address", async () => {
    stubApi([
      userMessage,
      answer({
        content: "Case claim.",
        citations: [{ ...caseCitation, sourceUrl: "javascript:alert(1)" }],
        claims: [{ text: "Case claim.", citationIds: ["commonlii-LKCA-1999-1"] }],
      }),
    ]);
    renderWithIntl(<ResearchScreen />);
    await screen.findByText("Sources used");
    expect(screen.queryByRole("link", { name: "Open source" })).toBeNull();
  });

  it("keeps a statute-only answer free of case tags", async () => {
    stubApi([
      userMessage,
      answer({
        content: "Statute claim.",
        citations: [statuteCitation],
        claims: [{ text: "Statute claim.", citationIds: ["SRC011:s39"] }],
      }),
    ]);
    renderWithIntl(<ResearchScreen />);
    await screen.findByText("Sources used");
    expect(screen.getByText("Statute claim.").textContent).toBe("Statute claim.");
    expect(screen.queryByText("Case law", { selector: "h4" })).toBeNull();
  });

  it("explains when case-law search was unavailable", async () => {
    stubApi([userMessage, answer({ content: "research.insufficient.caseLawUnavailable", citations: [], claims: [] })]);
    renderWithIntl(<ResearchScreen />);
    expect(
      await screen.findByText("Case-law search is unavailable right now. Try again, or search statutes & amendments."),
    ).toBeTruthy();
  });
});
