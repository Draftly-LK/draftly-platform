// @vitest-environment happy-dom
import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";

vi.mock("next/navigation", () => ({ usePathname: () => "/matters", useRouter: () => ({ push: vi.fn() }) }));

import { Sidebar } from "./sidebar";
import { SidebarStateProvider } from "./sidebar-state";

beforeEach(() => {
  document.cookie = "draftly-sidebar=; max-age=0; path=/";
  delete document.documentElement.dataset.sidebar;
  window.matchMedia = ((query: string) => ({
    matches: query.includes("1024px"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  })) as unknown as typeof window.matchMedia;
});

const renderSidebar = (collapsed = false) =>
  renderWithIntl(
    <SidebarStateProvider initialCollapsed={collapsed}>
      <Sidebar />
    </SidebarStateProvider>,
  );

describe("Sidebar toggle", () => {
  it("is a button next to the logo: Collapse sidebar when open, with aria-expanded and the shortcut", () => {
    renderSidebar();
    const toggle = screen.getByRole("button", { name: "Collapse sidebar" });
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(toggle.getAttribute("aria-controls")).toBe("app-sidebar");
    expect(toggle.getAttribute("aria-keyshortcuts")).toBe("Control+\\");
    expect(document.getElementById("app-sidebar")).toBeTruthy();
    // Desktop only: hidden below 1024px, where the sidebar is a drawer.
    expect(toggle.className).toContain("hidden");
    expect(toggle.className).toContain("lg:inline-flex");
  });

  it("renders Expand sidebar, aria-expanded false, when the server said collapsed", () => {
    renderSidebar(true);
    const toggle = screen.getByRole("button", { name: "Expand sidebar" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
  });

  it("clicking it collapses, remembers the choice in the cookie and the html attribute, and expands again", () => {
    renderSidebar();
    fireEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(screen.getByRole("button", { name: "Expand sidebar" }).getAttribute("aria-expanded")).toBe("false");
    expect(document.documentElement.dataset.sidebar).toBe("collapsed");
    expect(document.cookie).toContain("draftly-sidebar=collapsed");
    fireEvent.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(document.documentElement.dataset.sidebar).toBe("expanded");
  });

  it("Ctrl+backslash does the same from the keyboard", () => {
    renderSidebar();
    fireEvent.keyDown(window, { key: "\\", ctrlKey: true });
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeTruthy();
  });
});

describe("Sidebar rail styling", () => {
  it("hides the wordmark, group labels and recent matters in the rail, keeping the logo mark", () => {
    const { container } = renderSidebar();
    const aside = container.querySelector("aside") as HTMLElement;
    expect(within(aside).getByText("Notarial workspace").parentElement?.className).toContain("rail:hidden");
    expect(within(aside).getByText("Work").className).toContain("rail:hidden");
    expect(within(aside).getByText("Knowledge").className).toContain("rail:hidden");
    expect(within(aside).getByText("Recent matters").parentElement?.className).toContain("rail:hidden");
    expect(aside.querySelector("img")).not.toBeNull();
  });

  it("nav links keep their names in the rail: the label is visually hidden, not removed", () => {
    renderSidebar();
    const matters = screen.getByRole("link", { name: "Matters" });
    expect(matters.querySelector("span")?.className).toContain("rail:sr-only");
    expect(matters.className).toContain("rail:justify-center");
    expect(screen.getByRole("link", { name: "Home" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Legal sources" })).toBeTruthy();
  });

  it("the search field and the account area shrink to an icon and an avatar in the rail", () => {
    renderSidebar();
    const search = screen.getByRole("button", { name: "Search workspace" });
    expect(search.className).toContain("rail:w-10");
    expect(search.querySelector("kbd")?.className).toContain("rail:hidden");
    const account = screen.getByRole("button", { name: "Account menu" });
    expect(account.className).toContain("rail:justify-center");
  });

  it("the transition is 180ms on width, and the sidebar keeps its gold marker on the active item", () => {
    const { container } = renderSidebar();
    expect((container.querySelector("aside") as HTMLElement).className).toContain("duration-[180ms]");
    expect(screen.getByRole("link", { name: "Matters" }).className).toContain("before:bg-gold");
    expect(screen.getByRole("link", { name: "Matters" }).getAttribute("aria-current")).toBe("page");
  });
});

describe("Sidebar nav states", () => {
  it("hover is a lighter veil (white 5%) than the active item (white 10% plus the gold marker)", () => {
    renderSidebar();
    const active = screen.getByRole("link", { name: "Matters" });
    const idle = screen.getByRole("link", { name: "Home" });
    expect(active.className).toContain("bg-white/10");
    expect(active.className).toContain("before:bg-gold");
    expect(idle.className).toContain("hover:bg-white/5");
    expect(idle.className).not.toContain("bg-white/10");
    expect(idle.className).not.toContain("before:bg-gold");
  });
});
