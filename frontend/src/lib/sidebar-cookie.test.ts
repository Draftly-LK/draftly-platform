import { describe, expect, it } from "vitest";
import { parseSidebarCookie, SIDEBAR_COOKIE, sidebarCookieString } from "./sidebar-cookie";

describe("sidebar cookie", () => {
  it("reads collapsed only from the exact value; anything else is expanded", () => {
    expect(parseSidebarCookie("collapsed")).toBe(true);
    expect(parseSidebarCookie("expanded")).toBe(false);
    expect(parseSidebarCookie("COLLAPSED")).toBe(false);
    expect(parseSidebarCookie("")).toBe(false);
    expect(parseSidebarCookie(undefined)).toBe(false);
    expect(parseSidebarCookie(null)).toBe(false);
  });

  it("writes a year-long, site-wide, same-site cookie the parser reads back", () => {
    for (const collapsed of [true, false]) {
      const text = sidebarCookieString(collapsed);
      expect(text).toContain("path=/");
      expect(text).toContain("max-age=31536000");
      expect(text).toContain("SameSite=Lax");
      const value = text.split(";")[0]?.split("=")[1];
      expect(parseSidebarCookie(value)).toBe(collapsed);
      expect(text.startsWith(`${SIDEBAR_COOKIE}=`)).toBe(true);
    }
  });
});
