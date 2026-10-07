// @vitest-environment happy-dom
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithIntl } from "@/test/render";
import { MatterStepper } from "./matter-stepper";

describe("MatterStepper", () => {
  it("ticks finished stages, marks the current one and names every step", () => {
    renderWithIntl(<MatterStepper state="REVIEW_REQUIRED" />);
    const steps = within(screen.getByRole("list", { name: "Matter progress" })).getAllByRole("listitem");
    expect(steps).toHaveLength(6);
    expect(steps[2]?.getAttribute("aria-current")).toBe("step");
    expect(steps[0]?.textContent).toContain("Intake (completed)");
    expect(steps[1]?.textContent).toContain("Evidence (completed)");
    expect(steps[3]?.textContent).not.toContain("completed");
    expect(screen.getByText("Step 3 of 6: Review")).toBeTruthy();
  });

  it("shows a hold on the stage it interrupted, in words as well as colour", () => {
    renderWithIntl(<MatterStepper state="LITIGATION_HOLD" />);
    const current = screen.getAllByRole("listitem").find((step) => step.getAttribute("aria-current") === "step");
    expect(current?.textContent).toContain("Review (on hold)");
  });

  it("is complete once the matter is registered", () => {
    renderWithIntl(<MatterStepper state="REGISTERED" />);
    expect(screen.getAllByRole("listitem").every((step) => step.textContent?.includes("completed"))).toBe(true);
    expect(screen.getByText("All stages complete")).toBeTruthy();
  });
});
