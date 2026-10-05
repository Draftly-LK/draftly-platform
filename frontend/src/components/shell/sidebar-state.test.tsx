// @vitest-environment happy-dom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { isRailActive, SidebarStateProvider, useSidebarState } from "./sidebar-state";

function Probe() {
  const { collapsed, toggle } = useSidebarState();
  return (
    <button onClick={toggle} data-collapsed={String(collapsed)}>
      probe
    </button>
  );
}

function setDesktop(matches: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: query.includes("1024px") ? matches : false,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  })) as unknown as typeof window.matchMedia;
}

const clearCookie = () => {
  document.cookie = "draftly-sidebar=; max-age=0; path=/";
};

beforeEach(() => {
  clearCookie();
  delete document.documentElement.dataset.sidebar;
  setDesktop(true);
});
afterEach(() => {
  cleanup();
  clearCookie();
});

const probe = () => screen.getByRole("button", { name: "probe" });
const press = (init: KeyboardEventInit) => act(() => void window.dispatchEvent(new KeyboardEvent("keydown", init)));

describe("SidebarStateProvider", () => {
  it("starts from the value the server read", () => {
    render(
      <SidebarStateProvider initialCollapsed>
        <Probe />
      </SidebarStateProvider>,
    );
    expect(probe().dataset.collapsed).toBe("true");
  });

  it("toggling flips the state, the cookie and the html data-sidebar attribute", () => {
    render(
      <SidebarStateProvider initialCollapsed={false}>
        <Probe />
      </SidebarStateProvider>,
    );
    fireEvent.click(probe());
    expect(probe().dataset.collapsed).toBe("true");
    expect(document.documentElement.dataset.sidebar).toBe("collapsed");
    expect(document.cookie).toContain("draftly-sidebar=collapsed");
    fireEvent.click(probe());
    expect(probe().dataset.collapsed).toBe("false");
    expect(document.documentElement.dataset.sidebar).toBe("expanded");
    expect(document.cookie).toContain("draftly-sidebar=expanded");
  });

  it("Ctrl+backslash toggles on desktop, Cmd+backslash too; Ctrl+B and a bare backslash do not", () => {
    render(
      <SidebarStateProvider initialCollapsed={false}>
        <Probe />
      </SidebarStateProvider>,
    );
    press({ key: "\\", ctrlKey: true });
    expect(probe().dataset.collapsed).toBe("true");
    press({ key: "\\", metaKey: true });
    expect(probe().dataset.collapsed).toBe("false");
    press({ key: "b", ctrlKey: true });
    press({ key: "\\" });
    expect(probe().dataset.collapsed).toBe("false");
  });

  it("the shortcut does nothing in the drawer layout below 1024px", () => {
    setDesktop(false);
    render(
      <SidebarStateProvider initialCollapsed={false}>
        <Probe />
      </SidebarStateProvider>,
    );
    press({ key: "\\", ctrlKey: true });
    expect(probe().dataset.collapsed).toBe("false");
  });
});

describe("isRailActive", () => {
  it("is true only when collapsed on a desktop-width screen", () => {
    document.documentElement.dataset.sidebar = "collapsed";
    expect(isRailActive()).toBe(true);
    setDesktop(false);
    expect(isRailActive()).toBe(false);
    setDesktop(true);
    document.documentElement.dataset.sidebar = "expanded";
    expect(isRailActive()).toBe(false);
  });
});
