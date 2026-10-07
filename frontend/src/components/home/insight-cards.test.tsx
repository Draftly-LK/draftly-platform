// @vitest-environment happy-dom
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithIntl } from "@/test/render";
import type { Obligation } from "@/types/obligation";
import type { ApiRtaMatter, RtaMatterState } from "@/types/rta";
import { InsightCards } from "./insight-cards";

const NOW = new Date("2026-07-22T10:00:00Z");

function feed(states: RtaMatterState[]) {
  return {
    loading: false,
    failed: false,
    matters: states.map((state, index) => ({ id: `m${index}`, reference: `RTA-SYN-${index}`, state, updatedAt: "2026-07-21T00:00:00Z" }) as ApiRtaMatter),
  };
}

const obligation = (id: string, dueDate: string): Obligation => ({ id, matterId: "m0", labelKey: "obligations.monthlyList", dueDate, status: "upcoming" });

describe("insight cards", () => {
  it("shows the pipeline with a legend that carries every number", () => {
    renderWithIntl(<InsightCards feed={feed(["EVIDENCE_COLLECTION", "REVIEW_REQUIRED", "REVIEW_REQUIRED", "DRAFTING"])} obligations={[]} now={NOW} />);
    const chart = screen.getByRole("img", { name: /4 open matters: 1 in progress, 2 to review, 1 in drafting/ });
    expect(chart).toBeTruthy();
    const legend = screen.getByText("To review").closest("li") as HTMLElement;
    expect(within(legend).getByText("2")).toBeTruthy();
    expect(screen.getByRole("link", { name: /View matters/ }).getAttribute("href")).toBe("/matters?status=open");
  });

  it("explains an empty pipeline instead of showing an empty chart alone", () => {
    renderWithIntl(<InsightCards feed={feed([])} obligations={[]} now={NOW} />);
    expect(screen.getByText("Your pipeline appears here once you create a matter.")).toBeTruthy();
  });

  it("counts what is due in the next 14 days and names the next date", () => {
    renderWithIntl(
      <InsightCards
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
    renderWithIntl(<InsightCards feed={feed([])} obligations={[]} now={NOW} />);
    expect(screen.getAllByText("Your research allowance shows once you're signed in.").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /Open Research/ }).getAttribute("href")).toBe("/research");
  });
});
