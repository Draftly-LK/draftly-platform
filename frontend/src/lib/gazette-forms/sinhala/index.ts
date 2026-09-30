import type { GazetteForm } from "../types";
import { form08Document } from "./form-08";
import { form12Document } from "./form-12";

/**
 * The Sinhala edition of Gazette 1886/58, kept apart from the served set. The
 * application does not import this module; tests and the development compare
 * view do, so the transcription stays checked.
 */
export const SINHALA_GAZETTE_FORMS: Record<string, GazetteForm> = {
  "rta.reg.2022.form.08": {
    templateId: "rta.reg.2022.form.08",
    formNumber: "08",
    language: "si",
    document: form08Document,
    pages: ["page-04.png", "page-05.png", "page-06.png"],
  },
  "rta.reg.2022.form.12": {
    templateId: "rta.reg.2022.form.12",
    formNumber: "12",
    language: "si",
    document: form12Document,
    pages: ["page-13.png", "page-14.png"],
  },
};
