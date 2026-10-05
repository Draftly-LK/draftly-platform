// @vitest-environment happy-dom
import { screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import type { ApiRtaMatter } from "@/types/rta";

const mocks = vi.hoisted(() => ({
  apiEnabled: false,
  feed: { matters: [] as unknown[], loading: false, failed: false },
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, isApiEnabled: () => mocks.apiEnabled };
});
vi.mock("@/lib/api/use-recent-matters", () => ({ useRecentMatters: () => mocks.feed }));

import { Dashboard } from "./dashboard";
import { RecentMatters } from "./recent-matters";
import { UpcomingObligations } from "./upcoming-obligations";

const NOW = new Date("2026-07-22T09:30:00.000Z");

const matter = (over: Partial<ApiRtaMatter>): ApiRtaMatter =>
  ({
    id: "m1",
    reference: "RTA-2026-AAA-0001",
    clientReference: "Client One",
    subtypeId: "lk.rta.instrument.transfer_sale",
    state: "DRAFTING",
    updatedAt: "2026-07-22T07:30:00.000Z",
    ...over,
  }) as ApiRtaMatter;

const feedOf = (matters: ApiRtaMatter[]) => ({ matters, loading: false, failed: false });

beforeEach(() => {
  mocks.apiEnabled = false;
  mocks.feed = { matters: [], loading: false, failed: false };
});

describe("RecentMatters", () => {
  it("lists review-required matters first, flagged, each with one link", () => {
    renderWithIntl(
      <RecentMatters
        now={NOW}
        feed={feedOf([
          matter({ id: "a", reference: "REF-A", clientReference: "Alpha", state: "DRAFTING" }),
          matter({ id: "b", reference: "REF-B", clientReference: "Bravo", state: "REVIEW_REQUIRED", updatedAt: "2026-07-01T00:00:00Z" }),
        ])}
      />,
    );
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(within(rows[0] as HTMLElement).getByText("Bravo")).toBeTruthy();
    expect(rows[0]?.className).toContain("before:bg-amber");
    expect(rows[1]?.className).not.toContain("before:bg-amber");
    expect(within(rows[0] as HTMLElement).getAllByRole("link")).toHaveLength(1);
    expect(within(rows[0] as HTMLElement).getByRole("link", { name: /Review/ })).toBeTruthy();
    expect(within(rows[1] as HTMLElement).getByRole("link", { name: /Open/ })).toBeTruthy();
  });

  it("shows the status as an icon plus words, and relative activity inside a week", () => {
    const { container } = renderWithIntl(<RecentMatters now={NOW} feed={feedOf([matter({ state: "REVIEW_REQUIRED" })])} />);
    expect(screen.getAllByText("Review required").length).toBeGreaterThan(0);
    expect(container.querySelector("li svg[aria-hidden='true']")).not.toBeNull();
    expect(screen.getByText(/2 hours ago/)).toBeTruthy();
  });

  it("prints older activity as a day-month date", () => {
    renderWithIntl(<RecentMatters now={NOW} feed={feedOf([matter({ updatedAt: "2026-06-03T10:00:00.000Z" })])} />);
    expect(screen.getByText("3 Jun")).toBeTruthy();
  });

  it("caps the list at eight rows", () => {
    const many = Array.from({ length: 12 }, (_, i) => matter({ id: `m${i}`, reference: `REF-${i}`, clientReference: `Client ${i}` }));
    renderWithIntl(<RecentMatters now={NOW} feed={feedOf(many)} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(8);
  });

  it("says what happened when the feed fails", () => {
    renderWithIntl(<RecentMatters now={NOW} feed={{ matters: [], loading: false, failed: true }} />);
    expect(screen.getByText("Recent matters could not be loaded.")).toBeTruthy();
  });
});

describe("UpcomingObligations", () => {
  const obligation = (id: string, dueDate: string) => ({
    id,
    matterId: "m1",
    labelKey: "obligations.monthlyList",
    dueDate,
    status: "upcoming" as const,
  });

  it("words each due date by urgency and puts the most urgent first", () => {
    renderWithIntl(
      <UpcomingObligations
        now={NOW}
        feed={feedOf([matter({})])}
        obligations={[obligation("far", "2026-08-01"), obligation("soon", "2026-07-24"), obligation("late", "2026-07-20"), obligation("today", "2026-07-22")]}
      />,
    );
    const items = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(items[0]).toContain("Overdue by 2 days");
    expect(items[1]).toContain("Due today");
    expect(items[2]).toContain("In 2 days");
    expect(items[3]).toContain("1 Aug");
    expect(items[0]).toContain("RTA-2026-AAA-0001");
  });

  it("colours overdue as danger and the next two days as warning, always beside an icon", () => {
    const { container } = renderWithIntl(
      <UpcomingObligations now={NOW} feed={feedOf([])} obligations={[obligation("late", "2026-07-20"), obligation("soon", "2026-07-24")]} />,
    );
    expect(container.querySelector("li:nth-child(1) .text-red")).not.toBeNull();
    expect(container.querySelector("li:nth-child(2) .text-amber-text")).not.toBeNull();
    expect(container.querySelectorAll("li svg[aria-hidden='true']")).toHaveLength(2);
  });

  it("says so quietly when nothing is due in 14 days", () => {
    renderWithIntl(<UpcomingObligations now={NOW} feed={feedOf([])} obligations={[obligation("far", "2026-12-01")]} />);
    expect(screen.getByText("Nothing due in the next 14 days.")).toBeTruthy();
  });
});

describe("Dashboard", () => {
  it("has exactly one gold button when there is data, and each count opens its filtered list", () => {
    const { container } = renderWithIntl(<Dashboard obligations={[]} />);
    expect(container.querySelectorAll(".bg-gold")).toHaveLength(1);
    expect(screen.getByRole("link", { name: /Create a matter/ }).className).toContain("bg-gold");
    expect(screen.getByRole("link", { name: /Ask a legal question/ })).toBeTruthy();
    expect(screen.getByText("To review")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Open matters/ }).getAttribute("href")).toBe("/matters?status=open");
    expect(screen.getByRole("link", { name: /To review/ }).getAttribute("href")).toBe("/matters?status=review");
    expect(screen.getByRole("link", { name: /In drafting/ }).getAttribute("href")).toBe("/matters?status=drafting");
  });

  it("centres each count under its label; To review is amber label and number together, with no icon", () => {
    const { container } = renderWithIntl(<Dashboard obligations={[]} />);
    const counts = container.querySelectorAll("section[aria-label] ul > li a");
    expect(counts).toHaveLength(3);
    for (const link of counts) {
      expect(link.className).toContain("items-center");
      expect(link.className).toContain("text-center");
    }
    const review = screen.getByRole("link", { name: /To review/ });
    const [label, number] = review.querySelectorAll("span");
    expect(label?.className).toContain("text-amber-on-dark");
    expect(number?.className).toContain("text-amber-on-dark");
    expect(review.querySelector("svg")).toBeNull();
    // A count of zero stays muted, label and number alike.
    const drafting = screen.getByRole("link", { name: /In drafting/ });
    expect(drafting.querySelector("span")?.className).toContain("text-on-dark-muted");
  });

  it("gives the two header buttons one width", () => {
    renderWithIntl(<Dashboard obligations={[]} />);
    const group = screen.getByRole("link", { name: /Create a matter/ }).parentElement as HTMLElement;
    expect(group.className).toContain("auto-cols-fr");
    expect(group.className).toContain("grid-flow-col");
    expect(group.querySelectorAll("a")).toHaveLength(2);
  });

  it("offers planned workflows as a quiet, unfocusable Coming soon line", () => {
    renderWithIntl(<Dashboard obligations={[]} />);
    expect(screen.getByText("Coming soon")).toBeTruthy();
    const planned = screen.getAllByRole("link", { hidden: true }).filter((el) => el.getAttribute("aria-disabled") === "true");
    expect(planned.length).toBeGreaterThan(0);
    for (const el of planned) expect(el.getAttribute("href")).toBeNull();
  });

  it("with no matters, shows the first-run panel instead of counts and keeps one gold button", () => {
    mocks.apiEnabled = true;
    const { container } = renderWithIntl(<Dashboard obligations={[]} />);
    expect(screen.getByRole("heading", { name: "Start your first matter" })).toBeTruthy();
    expect(screen.getByText("Start a matter or ask a legal question.")).toBeTruthy();
    expect(screen.queryByText("To review")).toBeNull();
    expect(container.querySelectorAll(".bg-gold")).toHaveLength(1);
    expect(screen.getAllByRole("link", { name: /Ask a legal question/ })).toHaveLength(1);
  });

  it("states how many matters need review", () => {
    mocks.apiEnabled = true;
    mocks.feed = feedOf([matter({ state: "REVIEW_REQUIRED" }), matter({ id: "m2", state: "LEGAL_REVIEW" })]);
    renderWithIntl(<Dashboard obligations={[]} />);
    expect(screen.getByText("2 matters need your review")).toBeTruthy();
  });
});
