import { ENGLISH_GAZETTE_FORMS } from "./english";
import type { GazetteForm } from "./types";

export * from "./types";

/**
 * Gazette renderings keyed by backend template id. A template without an entry
 * falls back to the field-by-field review only; nothing is guessed.
 *
 * The rendering is the English edition of Gazette 1886/58 (2014); the Sinhala
 * edition is kept in ./sinhala and is not served. The backend cites
 * the 2022 amendment for the same form numbers; whether the 2014 layout is the
 * current prescribed one is for the legal team to confirm.
 */
export const GAZETTE_FORMS: Record<string, GazetteForm> = ENGLISH_GAZETTE_FORMS;

export function gazetteFormFor(templateId: string): GazetteForm | undefined {
  return GAZETTE_FORMS[templateId];
}
