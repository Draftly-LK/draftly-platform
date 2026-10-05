/**
 * The sidebar's collapsed or expanded choice lives in a cookie so the server can
 * render the right state on the first paint (no flash, no hydration mismatch).
 * `collapsed` and `expanded` are the only values; anything else means expanded.
 */
export const SIDEBAR_COOKIE = "draftly-sidebar";

export type SidebarState = "collapsed" | "expanded";

export function parseSidebarCookie(value: string | null | undefined): boolean {
  return value === "collapsed";
}

/** A year, site-wide, not sent cross-site. Not a secret, so not HttpOnly: the client sets it. */
export function sidebarCookieString(collapsed: boolean): string {
  const value: SidebarState = collapsed ? "collapsed" : "expanded";
  return `${SIDEBAR_COOKIE}=${value}; path=/; max-age=31536000; SameSite=Lax`;
}
