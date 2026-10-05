"use client";

import { createContext, use, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { sidebarCookieString } from "@/lib/sidebar-cookie";

interface SidebarStateValue {
  collapsed: boolean;
  toggle: () => void;
}

const SidebarStateContext = createContext<SidebarStateValue>({ collapsed: false, toggle: () => undefined });

const DESKTOP = "(min-width: 1024px)";

/**
 * Whether the desktop sidebar is collapsed to its icon rail. The first value
 * comes from the cookie the server read, so server and client agree. Toggling
 * updates the state, the cookie and `<html data-sidebar>` (which the `rail:`
 * styles key on). Ctrl+\ (or Cmd+\) toggles it on desktop; Ctrl+B is left to the
 * editor, where it means bold.
 */
export function SidebarStateProvider({ initialCollapsed, children }: { initialCollapsed: boolean; children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(initialCollapsed);

  const apply = useCallback((next: boolean) => {
    setCollapsed(next);
    document.documentElement.dataset.sidebar = next ? "collapsed" : "expanded";
    document.cookie = sidebarCookieString(next);
  }, []);

  const toggle = useCallback(() => apply(!collapsed), [apply, collapsed]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey || event.key !== "\\") return;
      // The drawer below 1024px has no collapsed state, so the shortcut does nothing there.
      if (!window.matchMedia(DESKTOP).matches) return;
      event.preventDefault();
      toggle();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [toggle]);

  const value = useMemo(() => ({ collapsed, toggle }), [collapsed, toggle]);
  return <SidebarStateContext value={value}>{children}</SidebarStateContext>;
}

export function useSidebarState(): SidebarStateValue {
  return use(SidebarStateContext);
}

/** True while the desktop sidebar is showing as the 72px rail. Read at event time, not render time. */
export function isRailActive(): boolean {
  return document.documentElement.dataset.sidebar === "collapsed" && window.matchMedia(DESKTOP).matches;
}
