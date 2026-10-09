import { describe, expect, it, vi } from "vitest";
const cookie = vi.hoisted(() => ({ value: undefined as string | undefined }));
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: () => ({ value: cookie.value }) }),
}));
vi.mock("next-intl/server", () => ({
  getRequestConfig: (callback: unknown) => callback,
}));
import config from "./request";
import en from "./messages/en.json";
import si from "./messages/si.json";
describe("server locale preference", () => {
  it.each([
    ["si", "si", si],
    ["en", "en", en],
    [undefined, "en", en],
    ["fr", "en", en],
    ["../si", "en", en],
  ] as const)(
    "reads %s only through the allowlist",
    async (value, locale, messages) => {
      cookie.value = value;
      const result = await config({
        requestLocale: Promise.resolve(undefined),
      });
      expect(result.locale).toBe(locale);
      expect(result.messages).toBe(messages);
    },
  );
});
