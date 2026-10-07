// @vitest-environment happy-dom
import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";

// Every call answers with an empty, synthetic matter so the screen settles without a backend.
vi.mock("@/lib/api/use-token-provider", () => ({ useTokenProvider: () => async () => null }));
vi.mock("@/lib/api/agent", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, listAgentMessages: async () => ({ items: [], page: { hasMore: false, nextCursor: null } }) };
});
vi.mock("@/lib/api/matters", () => ({
  getMatter: async () => ({ reference: "RTA-SYN-0001", state: "EVIDENCE_COLLECTION" }),
  getChecklist: async () => null,
}));
vi.mock("@/lib/api/documents", () => ({ getDocumentInbox: async () => null }));
vi.mock("@/lib/api/facts", () => ({ listMatterFacts: async () => ({ items: [] }) }));
vi.mock("@/lib/api/checks", () => ({ listIssues: async () => ({ items: [] }) }));
vi.mock("@/lib/api/drafts", () => ({ listForms: async () => ({ items: [] }) }));
vi.mock("@/components/shell/app-shell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

import { MatterAssistantScreen } from "./assistant-screen";

beforeEach(() => {
  window.localStorage.clear();
});

describe("MatterAssistantScreen", () => {
  it("keeps its tools in the body, and offers the context as Research's icon row on narrow screens", async () => {
    renderWithIntl(<MatterAssistantScreen matterId="m1" />);
    expect(await screen.findByRole("button", { name: /New conversation/ })).toBeTruthy();
    expect(screen.queryByRole("banner")).toBeNull();
    expect(screen.queryByRole("button", { name: "Matter context" })).toBeNull();
    // One open button in the wide panel's header, one in the narrow row.
    expect(screen.getAllByRole("button", { name: /matter context/i }).length).toBeGreaterThan(0);
  });

  it("starts folded to an icon rail, opens and folds again, and remembers the choice", async () => {
    renderWithIntl(<MatterAssistantScreen matterId="m1" />);
    const panel = screen.getByRole("complementary", { name: "Matter context" });
    expect(panel.getAttribute("data-collapsed")).toBe("true");
    // The folded column and the narrow-screen row (hidden by CSS) both link each section.
    for (const link of screen.getAllByRole("link", { name: /^Documents:/ })) expect(link.getAttribute("href")).toBe("/matters/m1/documents");
    fireEvent.click(within(panel).getByRole("button", { name: "Show matter context" }));
    expect(panel.getAttribute("data-collapsed")).toBeNull();
    expect(window.localStorage.getItem("draftly-assistant-context")).toBe("open");
    fireEvent.click(within(panel).getByRole("button", { name: "Hide matter context" }));
    expect(panel.getAttribute("data-collapsed")).toBe("true");
    expect(window.localStorage.getItem("draftly-assistant-context")).toBe("collapsed");
  });
});
