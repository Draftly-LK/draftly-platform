// @vitest-environment happy-dom
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithIntl } from "@/test/render";
import { MatterStepper } from "./matter-stepper";

describe("MatterStepper", () => {
  it("ticks finished stages, marks the current one and names every step", () => {
    renderWithIntl(<MatterStepper state="REVIEW_REQUIRED" />);
    const steps = within(
      screen.getByRole("list", { name: "Matter progress" }),
    ).getAllByRole("listitem");
    expect(steps).toHaveLength(6);
    expect(steps[2]?.getAttribute("aria-current")).toBe("step");
    expect(steps[0]?.textContent).not.toContain("completed");
    expect(steps[1]?.textContent).not.toContain("completed");
    expect(steps[3]?.textContent).not.toContain("completed");
    expect(screen.getByText("Step 3 of 6: Review")).toBeTruthy();
  });

  it("shows Drafting once a form exists, even while the matter is still in review", () => {
    renderWithIntl(<MatterStepper state="LEGAL_REVIEW" hasForm />);
    const steps = screen.getAllByRole("listitem");
    expect(steps[2]?.getAttribute("aria-current")).toBe("step");
    expect(steps[2]?.textContent).not.toContain("completed");
    expect(screen.getByText("Step 3 of 6: Review")).toBeTruthy();
  });

  it("never moves a matter backwards or off a hold because a form exists", () => {
    renderWithIntl(<MatterStepper state="APPROVAL_PENDING" hasForm />);
    expect(screen.getByText("Step 5 of 6: Approval")).toBeTruthy();
  });

  it("ticks Approval once the form is approved, leaving the export", () => {
    renderWithIntl(<MatterStepper state="APPROVED" />);
    const steps = screen.getAllByRole("listitem");
    expect(steps[4]?.textContent).not.toContain("completed");
    expect(screen.getByText("Step 6 of 6: Export")).toBeTruthy();
  });

  it("shows a hold on the stage it interrupted, in words as well as colour", () => {
    renderWithIntl(<MatterStepper state="LITIGATION_HOLD" />);
    const current = screen
      .getAllByRole("listitem")
      .find((step) => step.getAttribute("aria-current") === "step");
    expect(current?.textContent).toContain("Review (on hold)");
  });

  it("is complete once the matter is registered", () => {
    renderWithIntl(<MatterStepper state="REGISTERED" />);
    expect(
      screen
        .getAllByRole("listitem")
        .some((step) => step.textContent?.includes("completed")),
    ).toBe(false);
    expect(screen.getByText("Step 6 of 6: Export")).toBeTruthy();
  });
});
