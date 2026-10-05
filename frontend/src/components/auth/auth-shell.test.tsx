// @vitest-environment happy-dom
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithIntl } from "@/test/render";
import { AuthShell } from "./auth-shell";

describe("AuthShell", () => {
  it("shows the brand and one plain line beside the form", () => {
    renderWithIntl(
      <AuthShell>
        <p>the form</p>
      </AuthShell>,
    );
    expect(screen.getByText("Draftly")).toBeTruthy();
    expect(screen.getByText("Drafting and matter management for Registration of Title practice.")).toBeTruthy();
    expect(screen.getByText("the form")).toBeTruthy();
  });

  it("puts the brand on the navy inverse surface and the form in the main landmark", () => {
    const { container } = renderWithIntl(
      <AuthShell>
        <p>the form</p>
      </AuthShell>,
    );
    expect(container.querySelector("aside[data-surface='inverse']")?.className).toContain("bg-surface-inverse");
    expect(screen.getByRole("main").textContent).toContain("the form");
  });

  it("has no gold button of its own: the one primary action is Clerk's", () => {
    const { container } = renderWithIntl(
      <AuthShell>
        <p>x</p>
      </AuthShell>,
    );
    expect(container.querySelectorAll(".bg-primary-bg")).toHaveLength(0);
  });
});
