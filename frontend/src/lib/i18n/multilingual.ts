/**
 * MULTILINGUAL_LANGUAGE_SUPPORT gates the Sinhala UI locale.
 *
 * Default (unset or any value other than "false") → multilingual on.
 * "false" → English only: the `draftly-locale` cookie is ignored and the
 * locale toggle is not rendered.
 *
 * This gates the *interface* language only. Instrument/document language
 * (`DocumentLanguage`, matter instrument language) is matter data, not UI
 * chrome, and is unaffected.
 *
 * The variable is not NEXT_PUBLIC_, so it stays server-side; client
 * components read it through `MultilingualProvider` in the root layout.
 */
export const DEFAULT_LOCALE = "en" as const;

export type UiLocale = "en" | "si";

export function isMultilingualEnabled(): boolean {
  return process.env.MULTILINGUAL_LANGUAGE_SUPPORT !== "false";
}
