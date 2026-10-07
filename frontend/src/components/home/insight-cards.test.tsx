// @vitest-environment happy-dom
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithIntl } from "@/test/render";
import type { Obligation } from "@/types/obligation";
import type { ApiRtaMatter, RtaMatterState } from "@/types/rta";
import { PracticeInsights } from "./insight-cards";
import { OFFLINE_RESEARCH, type ResearchOverview } from "./use-research-overview";

const NOW = new Date("2026-07-22T10:00:00Z");

function feed(states: RtaMatterState[]) {
  return {
    loading: false,
    failed: false,
    matters: states.map((state, index) => ({ id: `m${index}`, reference: `RTA-SYN-${index}`, state, updatedAt: "2026-07-21T00:00:00Z" }) as ApiRtaMatter),
  };
}

const obligation = (id: string, dueDate: string): Obligation => ({ id, matterId: "m0", labelKey: "obligations.monthlyList", dueDate, status: "upcoming" });

describe("practice insights", () => {
  it("shows the pipeline with a legend that carries every number", () => {
    renderWithIntl(<PracticeInsights research={OFFLINE_RESEARCH} feed={feed(["EVIDENCE_COLLECTION", "REVIEW_REQUIRED", "REVIEW_REQUIRED", "DRAFTING"])} obligations={[]} now={NOW} />);
    const chart = screen.getByRole("img", { name: /4 open matters: 1 in progress, 2 to review, 1 in drafting/ });
    expect(chart).toBeTruthy();
    const legend = screen.getByText("To review").closest("li") as HTMLElement;
    expect(within(legend).getByText("2")).toBeTruthy();
    expect(screen.getByRole("link", { name: /View matters/ }).getAttribute("href")).toBe("/matters?status=open");
  });

  it("explains an empty pipeline instead of showing an empty chart alone", () => {
    renderWithIntl(<PracticeInsights research={OFFLINE_RESEARCH} feed={feed([])} obligations={[]} now={NOW} />);
    expect(screen.getByText("Your pipeline appears here once you create a matter.")).toBeTruthy();
  });

  it("counts what is due in the next 14 days and names the next date", () => {
    renderWithIntl(
      <PracticeInsights research={OFFLINE_RESEARCH}
        feed={feed([])}
        obligations={[obligation("a", "2026-07-23"), obligation("b", "2026-07-31"), obligation("c", "2026-09-30")]}
        now={NOW}
      />,
    );
    expect(screen.getByText(/2 obligations due/)).toBeTruthy();
    expect(screen.getByText(/next Jul 23|next 23 Jul/)).toBeTruthy();
    expect(screen.getByRole("img", { name: /2 obligations due in the next 14 days/ })).toBeTruthy();
  });

  it("shows no research figures offline rather than a misleading zero", () => {
    renderWithIntl(<PracticeInsights research={OFFLINE_RESEARCH} feed={feed([])} obligations={[]} now={NOW} />);
    expect(screen.getAllByText("Your research activity shows once you're signed in.").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /Open Research/ }).getAttribute("href")).toBe("/research");
  });

  it("splits research chats into active this month and earlier, and links the latest", () => {
    const chat = (id: string, title: string, updatedAt: string) =>
      ({ id, title, createdAt: updatedAt, updatedAt }) as NonNullable<ResearchOverview["conversations"]>[number];
    const research: ResearchOverview = {
      state: "ready",
      conversations: [chat("c1", "Stamp duty on a gift", "2026-07-21T00:00:00Z"), chat("c2", "Prescription", "2026-07-02T00:00:00Z"), chat("c3", "Old question", "2026-05-10T00:00:00Z")],
      usage: { used: 10, limit: null, periodEnd: "2026-07-31T00:00:00Z" },
    };
    renderWithIntl(<PracticeInsights research={research} feed={feed([])} obligations={[]} now={NOW} />);
    expect(screen.getByRole("img", { name: "3 research chats: 2 active this month, 1 earlier." })).toBeTruthy();
    expect(within(screen.getByText("Active this month").closest("li") as HTMLElement).getByText("2")).toBeTruthy();
    expect(screen.getByText("10 research questions asked.")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Latest chat.*Stamp duty on a gift/ }).getAttribute("href")).toBe("/research");
  });

  it("is one card with three panels", () => {
    const { container } = renderWithIntl(<PracticeInsights research={OFFLINE_RESEARCH} feed={feed([])} obligations={[]} now={NOW} />);
    expect(container.querySelectorAll(".home-insights > .home-insight-panel")).toHaveLength(3);
  });
});
