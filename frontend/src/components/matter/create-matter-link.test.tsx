// @vitest-environment happy-dom
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithIntl } from "@/test/render";
import { CreateMatterLink } from "./create-matter-link";

describe("CreateMatterLink", () => {
  it("says Create a matter with the file-plus icon, opens the wizard, and is the shared primary button", () => {
    const { container } = renderWithIntl(<CreateMatterLink />);
    const link = screen.getByRole("link", { name: "Create a matter" });
    expect(link.getAttribute("href")).toBe("/new");
    expect(link.className).toContain("bg-primary-bg");
    expect(link.className).toContain("min-h-10");
    expect(link.className).toContain("min-w-48");
    expect(container.querySelector("svg.lucide-file-plus2")).not.toBeNull();
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });
});
