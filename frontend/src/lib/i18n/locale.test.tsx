// @vitest-environment happy-dom
import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render";
import { parseLocaleCookie, LOCALE_COOKIE } from "./multilingual";
import { LocaleSwitch } from "@/components/shell/locale-switch";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

describe("persisted interface language", () => {
  it("allowlists only en and si with an English fallback", () => {
    expect(parseLocaleCookie("si")).toBe("si");
    for (const invalid of [undefined, "", "SI", "fr", "../../en", "si%00"]) {
      expect(parseLocaleCookie(invalid)).toBe("en");
    }
  });
  it("provides an accessible shell switch and persists a reload-readable preference", () => {
    renderWithIntl(<LocaleSwitch />);
    fireEvent.click(screen.getByRole("button", { name: "සිංහල" }));
    expect(document.cookie).toContain(`${LOCALE_COOKIE}=si`);
    expect(refresh).toHaveBeenCalledOnce();
    expect(parseLocaleCookie(document.cookie.split("=").at(-1))).toBe("si");
  });
  it("renders the Sinhala control using the actual catalogue", () => {
    renderWithIntl(<LocaleSwitch />, "si");
    expect(
      screen.getByRole("group", { name: "අතුරුමුහුණත් භාෂාව" }),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("button", { name: "සිංහල" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
  });
});
