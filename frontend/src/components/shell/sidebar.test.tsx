// @vitest-environment happy-dom
import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";

vi.mock("next/navigation", () => ({ usePathname: () => "/matters", useRouter: () => ({ push: vi.fn() }) }));

import { Sidebar } from "./sidebar";
import { SidebarStateProvider } from "./sidebar-state";
import { SidebarToggle } from "./sidebar-toggle";

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

// The shell renders the collapse button first (so the keyboard reaches it first), then the sidebar.
const renderShell = (collapsed = false) =>
  renderWithIntl(
    <SidebarStateProvider initialCollapsed={collapsed}>
      <SidebarToggle />
      <Sidebar />
    </SidebarStateProvider>,
  );

const toggles = () => document.querySelectorAll("button[aria-controls='app-sidebar']");

describe("Sidebar collapse button", () => {
  it("is exactly one button, outside the sidebar, so the sidebar's clipping cannot cut it off", () => {
    const { container } = renderShell();
    expect(toggles()).toHaveLength(1);
    const aside = container.querySelector("aside") as HTMLElement;
    expect(aside.contains(toggles()[0] as Element)).toBe(false);
    expect(aside.className).toContain("overflow-hidden");
  });

  it("is first in keyboard order: the first Tab lands on it, before the search field and the nav", () => {
    renderShell();
    const all = [...document.querySelectorAll<HTMLElement>("button, a[href]")];
    expect(all[0]).toBe(toggles()[0]);
  });

  it("is also the only toggle in the collapsed rail (no second one under the logo)", () => {
    renderShell(true);
    expect(toggles()).toHaveLength(1);
  });

  it("is Collapse sidebar with aria-expanded true and a left chevron when open", () => {
    renderShell();
    const toggle = screen.getByRole("button", { name: "Collapse sidebar" });
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(toggle.getAttribute("aria-controls")).toBe("app-sidebar");
    expect(toggle.getAttribute("aria-keyshortcuts")).toBe("Control+\\");
    expect(document.getElementById("app-sidebar")).toBeTruthy();
    expect(toggle.querySelector("svg.lucide-chevron-left")).not.toBeNull();
  });

  it("is Expand sidebar with aria-expanded false and a right chevron when the server said collapsed", () => {
    renderShell(true);
    const toggle = screen.getByRole("button", { name: "Expand sidebar" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(toggle.querySelector("svg.lucide-chevron-right")).not.toBeNull();
  });

  it("is a 32px circle with a 16px chevron inside a 40px hit area, filled to match the sidebar", () => {
    renderShell();
    const toggle = screen.getByRole("button", { name: "Collapse sidebar" });
    const circle = toggle.querySelector("span") as HTMLElement;
    expect(toggle.className).toContain("size-full");
    expect(circle.className).toContain("size-8");
    expect(circle.className).toContain("rounded-full");
    expect(circle.className).toContain("bg-[#1A2F52]");
    expect(circle.className).toContain("group-focus-visible:outline-ring-on-dark");
    expect(toggle.querySelector("svg")?.getAttribute("class")).toContain("size-4");
  });

  it("shows its ring on the outer (right) half only: a full 1px ring on ::before clipped to the right half, never a border", () => {
    renderShell();
    const circle = screen.getByRole("button", { name: "Collapse sidebar" }).querySelector("span") as HTMLElement;
    const classes = circle.className.split(" ");
    // The ring is the ::before pseudo-element: a full 1px circle at 22% white, clipped to its right half.
    expect(classes).toContain("before:border");
    expect(classes).toContain("before:border-white/[0.22]");
    expect(classes).toContain("before:rounded-full");
    expect(classes).toContain("before:[clip-path:inset(0_0_0_50%)]");
    // Not drawn on the element itself, and no border-right (that would colour a quarter of the circle).
    expect(classes).not.toContain("border");
    expect(classes.some((c) => /^border-r\b|^border-white/.test(c))).toBe(false);
    // Hover turns the ring gold and the icon lighter.
    expect(classes).toContain("group-hover:before:border-gold");
    expect(classes).toContain("group-hover:text-white");
  });

  it("is hit by clicks on the 40px area, and the anchor is exactly 40px square", () => {
    renderShell();
    const toggle = screen.getByRole("button", { name: "Collapse sidebar" });
    const anchor = toggle.parentElement as HTMLElement;
    expect(anchor.style.width).toBe("40px");
    expect(anchor.style.height).toBe("40px");
  });

  it("sits on the sidebar's right edge, level with the logo, above the sidebar and its shadow, and slides with it", () => {
    renderShell();
    const anchor = screen.getByRole("button", { name: "Collapse sidebar" }).parentElement as HTMLElement;
    expect(anchor.style.left).toBe("calc(var(--sidebar-width) - 20px)");
    // 12px sidebar padding plus half of the 64px logo row, minus half the 40px hit area.
    expect(anchor.style.top).toBe("24px");
    expect(anchor.className).toContain("z-30");
    expect(anchor.className).toContain("fixed");
    expect(anchor.className).toContain("transition-[left]");
    expect(anchor.className).toContain("duration-[180ms]");
    expect(anchor.className).toContain("hidden");
    expect(anchor.className).toContain("lg:block");
  });

  it("collapses on click, remembers the choice, and expands again", () => {
    renderShell();
    fireEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(screen.getByRole("button", { name: "Expand sidebar" }).getAttribute("aria-expanded")).toBe("false");
    expect(document.documentElement.dataset.sidebar).toBe("collapsed");
    expect(document.cookie).toContain("draftly-sidebar=collapsed");
    fireEvent.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(document.documentElement.dataset.sidebar).toBe("expanded");
  });

  it("Ctrl+backslash does the same from the keyboard", () => {
    renderShell();
    fireEvent.keyDown(window, { key: "\\", ctrlKey: true });
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeTruthy();
  });
});

describe("Sidebar rail styling", () => {
  it("keeps the logo mark in the same single top row and hides the wordmark, group labels and recent matters", () => {
    const { container } = renderShell();
    const aside = container.querySelector("aside") as HTMLElement;
    const row = aside.querySelector("img")?.parentElement as HTMLElement;
    expect(row.className).toContain("rail:justify-center");
    expect(row.className).not.toContain("rail:flex-col");
    // The mark is 28px in the rail so the 32px button on the edge stays 6px clear of it.
    expect(aside.querySelector("img")?.className).toContain("rail:size-7");
    expect(within(aside).getByText("Notarial workspace").parentElement?.className).toContain("rail:hidden");
    expect(within(aside).getByText("Work").className).toContain("rail:hidden");
    expect(within(aside).getByText("Knowledge").className).toContain("rail:hidden");
    expect(within(aside).getByText("Recent matters").parentElement?.className).toContain("rail:hidden");
  });

  it("nav links keep their names in the rail: the label is visually hidden, not removed", () => {
    renderShell();
    const matters = screen.getByRole("link", { name: "Matters" });
    expect(matters.querySelector("span")?.className).toContain("rail:sr-only");
    expect(matters.className).toContain("rail:justify-center");
    expect(screen.getByRole("link", { name: "Home" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Legal sources" })).toBeTruthy();
  });

  it("the search field and the account area shrink to an icon and an avatar in the rail", () => {
    renderShell();
    const search = screen.getByRole("button", { name: "Search workspace" });
    expect(search.className).toContain("rail:w-10");
    expect(search.querySelector("kbd")?.className).toContain("rail:hidden");
    expect(screen.getByRole("button", { name: "Account menu" }).className).toContain("rail:justify-center");
  });

  it("the sidebar width transitions in 180ms, and the active item keeps its gold marker", () => {
    const { container } = renderShell();
    expect((container.querySelector("aside") as HTMLElement).className).toContain("duration-[180ms]");
    expect(screen.getByRole("link", { name: "Matters" }).className).toContain("before:bg-gold");
    expect(screen.getByRole("link", { name: "Matters" }).getAttribute("aria-current")).toBe("page");
  });
});

describe("Sidebar nav states", () => {
  it("hover is a lighter veil (white 5%) than the active item (white 10% plus the gold marker)", () => {
    renderShell();
    const active = screen.getByRole("link", { name: "Matters" });
    const idle = screen.getByRole("link", { name: "Home" });
    expect(active.className).toContain("bg-white/10");
    expect(active.className).toContain("before:bg-gold");
    expect(idle.className).toContain("hover:bg-white/5");
    expect(idle.className).not.toContain("bg-white/10");
    expect(idle.className).not.toContain("before:bg-gold");
  });
});
