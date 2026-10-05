// @vitest-environment happy-dom
import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => "/" }));

import { CommandPalette } from "./command-palette";

describe("CommandPalette", () => {
  it("the sidebar search field has a soft light border that strengthens on hover, and stays a pill", () => {
    renderWithIntl(<CommandPalette tone="dark" />);
    const field = screen.getByRole("button", { name: /Search workspace/ });
    expect(field.className).toContain("border-white/15");
    expect(field.className).toContain("hover:border-white/25");
    expect(field.className).toContain("rounded-control");
  });

  it("opens with an active search row: even padding, one centred line, a soft bottom rule, no ring on the input", () => {
    renderWithIntl(<CommandPalette tone="dark" />);
    fireEvent.click(screen.getByRole("button", { name: /Search workspace/ }));
    const input = screen.getByPlaceholderText(/Search matters/);
    const row = input.parentElement as HTMLElement;
    expect(row.className).toContain("px-4");
    expect(row.className).toContain("py-3.5");
    expect(row.className).toContain("gap-3");
    expect(row.className).toContain("items-center");
    expect(row.className).toContain("border-b");
    expect(row.className).toContain("border-border-active");
    expect(input.className).toContain("focus-visible:outline-none");
    expect(screen.getByRole("button", { name: "Close" })).toBeTruthy();
  });
});
