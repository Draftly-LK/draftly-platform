/**
 * The interface is English only. Sinhala strings stay in the catalogue
 * (`messages/si.json`) for a later release but are not served: there is no
 * language switch and any stored `draftly-locale` cookie is ignored.
 *
 * This is interface language only. Instrument/document language
 * (`DocumentLanguage`, matter instrument language) is matter data, not UI
 * chrome, and is unaffected.
 */
export const DEFAULT_LOCALE = "en" as const;

export type UiLocale = "en" | "si";
