// @vitest-environment happy-dom
import { fireEvent, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import type { ApiRtaMatter } from "@/types/rta";

const mocks = vi.hoisted(() => ({
  search: "",
  feed: { matters: [] as unknown[], loading: false, failed: false },
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(mocks.search),
  usePathname: () => "/matters",
}));
vi.mock("@/components/shell/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
vi.mock("@/components/shell/page-header", () => ({
  PageHeader: ({ title, action }: { title: string; action?: ReactNode }) => (
    <header>
      <h1>{title}</h1>
      {action}
    </header>
  ),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, isApiEnabled: () => true };
});
vi.mock("@/lib/api/use-recent-matters", () => ({ useRecentMatters: () => mocks.feed }));

import { MattersScreen } from "./matters-screen";

const matter = (id: string, state: ApiRtaMatter["state"], over: Partial<ApiRtaMatter> = {}): ApiRtaMatter =>
  ({
    id,
    reference: `REF-${id}`,
    clientReference: `Client ${id}`,
    subtypeId: "lk.rta.instrument.transfer_sale",
    state,
    updatedAt: "2026-07-22T07:30:00.000Z",
    ...over,
  }) as ApiRtaMatter;

const MATTERS = [
  matter("a", "DRAFTING"),
  matter("b", "REVIEW_REQUIRED"),
  matter("c", "LEGAL_REVIEW"),
  matter("d", "APPROVED"),
  matter("e", "CLOSED"),
];

beforeEach(() => {
  mocks.search = "";
  mocks.feed = { matters: MATTERS, loading: false, failed: false };
});

const shownRefs = () => screen.getAllByRole("row").slice(1).map((row) => within(row).getAllByRole("link")[0]?.textContent?.trim().split(" ")[0]);

describe("MattersScreen", () => {
  it("lists every matter with no filter, and has one gold button", () => {
    const { container } = renderWithIntl(<MattersScreen />);
    expect(shownRefs()).toEqual(["REF-a", "REF-b", "REF-c", "REF-d", "REF-e"]);
    expect(container.querySelectorAll(".bg-primary-gradient")).toHaveLength(1);
  });

  it.each([
    ["open", ["REF-a", "REF-b", "REF-c", "REF-d"]],
    ["review", ["REF-b", "REF-c"]],
    ["drafting", ["REF-a"]],
  ])("?status=%s shows exactly the matters its dashboard count counts", (status, expected) => {
    mocks.search = `status=${status}`;
    renderWithIntl(<MattersScreen />);
    expect(shownRefs()).toEqual(expected);
  });

  it("ignores an unknown status instead of showing an empty list", () => {
    mocks.search = "status=nonsense";
    renderWithIntl(<MattersScreen />);
    expect(shownRefs()).toHaveLength(5);
  });

  it("offers each filter as a link with its count, marking the current one", () => {
    mocks.search = "status=review";
    renderWithIntl(<MattersScreen />);
    const nav = screen.getByRole("navigation", { name: "Filter matters by status" });
    const links = within(nav).getAllByRole("link");
    expect(links.map((l) => l.getAttribute("href"))).toEqual([
      "/matters",
      "/matters?status=open",
      "/matters?status=review",
      "/matters?status=drafting",
    ]);
    expect(links[0]?.textContent).toContain("5");
    expect(links[2]?.textContent).toContain("2");
    expect(links[2]?.getAttribute("aria-current")).toBe("true");
    expect(links[0]?.getAttribute("aria-current")).toBeNull();
  });

  it("explains an empty filter and offers the way back", () => {
    mocks.search = "status=drafting";
    mocks.feed = { matters: [matter("d", "APPROVED")], loading: false, failed: false };
    renderWithIntl(<MattersScreen />);
    expect(screen.getByRole("heading", { name: "No matters match this filter" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Show all matters" }).getAttribute("href")).toBe("/matters");
  });

  it("with no matters at all, invites the first one without a second gold button", () => {
    mocks.feed = { matters: [], loading: false, failed: false };
    const { container } = renderWithIntl(<MattersScreen />);
    expect(screen.getByRole("heading", { name: "No matters yet" })).toBeTruthy();
    // The header carries the one gold button; the empty state offers the same action as a secondary link.
    const links = screen.getAllByRole("link", { name: "Create a matter" });
    expect(links).toHaveLength(2);
    expect(links.filter((l) => l.className.includes("bg-primary-gradient"))).toHaveLength(1);
    expect(container.querySelectorAll(".bg-primary-gradient")).toHaveLength(1);
  });

  it("shows a skeleton that announces itself while loading", () => {
    mocks.feed = { matters: [], loading: true, failed: false };
    renderWithIntl(<MattersScreen />);
    expect(screen.getByRole("status").textContent).toContain("Loading matters");
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("says what happened and how to fix it when the load fails, with a retry", () => {
    mocks.feed = { matters: [], loading: false, failed: true };
    renderWithIntl(<MattersScreen />);
    const alert = screen.getByRole("alert");
    expect(within(alert).getByRole("heading").textContent).toBe("Matters could not be loaded.");
    expect(alert.textContent).toContain("Check your connection");
    expect(within(alert).getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("gives each row one link that covers the whole row, and a status with an icon", () => {
    const { container } = renderWithIntl(<MattersScreen />);
    const row = screen.getAllByRole("row")[2] as HTMLElement;
    expect(within(row).getAllByRole("link")).toHaveLength(1);
    expect(within(row).getByRole("link").className).toContain("after:absolute");
    expect(within(row).getByText("Review required")).toBeTruthy();
    expect(container.querySelector("tbody svg[aria-hidden='true']")).not.toBeNull();
    fireEvent.click(within(row).getByRole("link"));
  });
});
