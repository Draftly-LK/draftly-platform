import type { GazetteForm } from "../types";
import { form08Document } from "./form-08";
import { form12Document } from "./form-12";

/** The English edition of Gazette 1886/58: the set the application serves. */
export const ENGLISH_GAZETTE_FORMS: Record<string, GazetteForm> = {
  "rta.reg.2022.form.08": {
    templateId: "rta.reg.2022.form.08",
    formNumber: "08",
    language: "en",
    document: form08Document,
    pages: ["page-04.png", "page-05.png", "page-06.png"],
  },
  "rta.reg.2022.form.12": {
    templateId: "rta.reg.2022.form.12",
    formNumber: "12",
    language: "en",
    document: form12Document,
    pages: ["page-14.png", "page-15.png"],
  },
};
