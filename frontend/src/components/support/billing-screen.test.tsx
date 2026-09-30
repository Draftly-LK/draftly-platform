// @vitest-environment happy-dom

import { screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";

const mocks = vi.hoisted(() => ({
  getBillingSubscription: vi.fn(),
  isApiEnabled: vi.fn(),
}));

vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));

vi.mock("@/components/shell/page-header", () => ({
  PageHeader: ({
    title,
    description,
  }: {
    title: string;
    description?: string;
  }) => (
    <header>
      <h1>{title}</h1>
      {description ? <p>{description}</p> : null}
    </header>
  ),
}));

vi.mock("@/lib/api/billing", () => ({
  getBillingSubscription: mocks.getBillingSubscription,
}));

vi.mock("@/lib/api/client", () => ({
  isApiEnabled: mocks.isApiEnabled,
}));

vi.mock("@/lib/api/use-token-provider", () => ({
  useTokenProvider: () => vi.fn().mockResolvedValue("synthetic-token"),
}));

import { BillingScreen } from "./billing-screen";

describe("BillingScreen", () => {
  beforeEach(() => {
    mocks.isApiEnabled.mockReturnValue(false);
    mocks.getBillingSubscription.mockReset();
  });

  it("shows the pilot and illustrative single-user plans without live billing", () => {
    renderWithIntl(<BillingScreen />);

    expect(screen.getByText("Draftly Pilot")).toBeTruthy();
    expect(screen.getByText("Illustrative post-pilot plans")).toBeTruthy();
    expect(screen.getByText("Recommended")).toBeTruthy();
    expect(screen.getAllByRole("article")).toHaveLength(3);
    expect(screen.getAllByRole("link", { name: /contact/i })).toHaveLength(2);

    const copy = screen.getByRole("main").textContent ?? "";
    expect(copy).not.toMatch(
      /\b(?:organisation|organization|firm|team seats|workspace administrator)\b/i,
    );
  });

  it("uses authoritative subscription status and pilot dates when available", async () => {
    mocks.isApiEnabled.mockReturnValue(true);
    mocks.getBillingSubscription.mockResolvedValue({
      id: "sub_synthetic",
      userId: "usr_synthetic",
      planVersionId: "plan_trial_v1",
      provider: "stub",
      status: "restricted",
      currentPeriodStart: "2026-09-01T12:00:00Z",
      currentPeriodEnd: "2026-09-30T12:00:00Z",
      trialEndsAt: "2026-09-30T12:00:00Z",
      cancelAtPeriodEnd: false,
      gracePeriodEndsAt: null,
      version: 1,
    });

    renderWithIntl(<BillingScreen />);

    await waitFor(() => expect(screen.getByText("Action needed")).toBeTruthy());
    expect(
      screen.getByText(/Pilot period: Sep 1, 2026 to Sep 30, 2026/),
    ).toBeTruthy();
  });

  it("falls back quietly without dates when the subscription endpoint fails", async () => {
    mocks.isApiEnabled.mockReturnValue(true);
    mocks.getBillingSubscription.mockRejectedValue(new Error("unavailable"));

    renderWithIntl(<BillingScreen />);

    await waitFor(() =>
      expect(mocks.getBillingSubscription).toHaveBeenCalledOnce(),
    );
    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.queryByText(/Pilot period:/)).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
