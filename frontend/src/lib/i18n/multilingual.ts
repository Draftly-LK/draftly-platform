/**
 * Persisted interface language. Only supported catalogue names are accepted.
 *
 * This is interface language only. Instrument/document language
 * (`DocumentLanguage`, matter instrument language) is matter data, not UI
 * chrome, and is unaffected.
 */
export const DEFAULT_LOCALE = "en" as const;

export type UiLocale = "en" | "si";

export const LOCALE_COOKIE = "draftly-locale";

export function parseLocaleCookie(value: string | undefined): UiLocale {
  return value === "si" ? "si" : DEFAULT_LOCALE;
}
