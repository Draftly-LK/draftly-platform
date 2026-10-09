// @vitest-environment happy-dom
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithIntl } from "@/test/render";
import { InlineAlert } from "./alert";
import { Button } from "./button";
import { ErrorState } from "./error-state";
import { RowsSkeleton, Skeleton } from "./skeleton";

describe("Skeleton", () => {
  it("is hidden from assistive tech and only animates when motion is allowed", () => {
    const { container } = renderWithIntl(<Skeleton className="h-4" />);
    const bar = container.firstElementChild as HTMLElement;
    expect(bar.getAttribute("aria-hidden")).toBe("true");
    expect(bar.className).toContain("motion-safe:animate-pulse");
  });

  it("RowsSkeleton announces one status and draws the requested number of rows", () => {
    const { container } = renderWithIntl(<RowsSkeleton label="Loading things" rows={3} />);
    expect(screen.getByRole("status").textContent).toBe("Loading things");
    expect(container.querySelectorAll("[role='status'] > div")).toHaveLength(3);
  });
});

describe("InlineAlert", () => {
  it("does not render warning notices", () => {
    const { container } = renderWithIntl(<InlineAlert tone="warning">Warning notice</InlineAlert>);
    expect(container.childElementCount).toBe(0);
    expect(screen.queryByText("Warning notice")).toBeNull();
  });
  it("errors are announced as alerts and carry an icon", () => {
    const { container } = renderWithIntl(<InlineAlert tone="danger">It broke</InlineAlert>);
    expect(screen.getByRole("alert").textContent).toBe("It broke");
    expect(container.querySelector("svg[aria-hidden='true']")).not.toBeNull();
  });

  it("notices are polite status messages, not alerts", () => {
    renderWithIntl(<InlineAlert tone="info">Heads up</InlineAlert>);
    expect(screen.getByRole("status").textContent).toBe("Heads up");
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("ErrorState", () => {
  it("says what happened, what to do, and offers the action", () => {
    renderWithIntl(
      <ErrorState title="Could not load" action={<Button>Try again</Button>}>
        Check your connection.
      </ErrorState>,
    );
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Could not load" })).toBeTruthy();
    expect(screen.getByText("Check your connection.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
