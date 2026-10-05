import en from "./messages/en.json";
import si from "./messages/si.json";
import type { CaseRecord, SimilarCase } from "@/types/case";

type LocaleLabels<T extends string> = Record<T, { en: string; si: string }>;

export const caseCollectionLabels: LocaleLabels<CaseRecord["collection"]> = {
  LKCA: { en: en.caseLaw.collections.LKCA, si: si.caseLaw.collections.LKCA },
  LKSC: { en: en.caseLaw.collections.LKSC, si: si.caseLaw.collections.LKSC },
};
export const caseSignalLabels: LocaleLabels<
  SimilarCase["matchedSignals"][number]
> = {
  lexical: { en: en.caseLaw.signals.lexical, si: si.caseLaw.signals.lexical },
  graph: { en: en.caseLaw.signals.graph, si: si.caseLaw.signals.graph },
  dense: { en: en.caseLaw.signals.dense, si: si.caseLaw.signals.dense },
};
export const caseQualityLabels: LocaleLabels<
  CaseRecord["qualityWarnings"][number]
> = {
  "encoding-errors": {
    en: en.caseLaw.warnings["encoding-errors"],
    si: si.caseLaw.warnings["encoding-errors"],
  },
  "missing-pages": {
    en: en.caseLaw.warnings["missing-pages"],
    si: si.caseLaw.warnings["missing-pages"],
  },
  "malformed-tags": {
    en: en.caseLaw.warnings["malformed-tags"],
    si: si.caseLaw.warnings["malformed-tags"],
  },
  "deciding-court-unparsed": {
    en: en.caseLaw.warnings["deciding-court-unparsed"],
    si: si.caseLaw.warnings["deciding-court-unparsed"],
  },
};
