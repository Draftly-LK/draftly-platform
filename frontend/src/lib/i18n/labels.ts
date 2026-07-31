import type { AuthorityType, AuthorityWeight, CheckStatus, CourtLevel, DocumentKind, DocumentRelation, IdentitySide, MatterType, ProcessingState, RegistrationRegime, StepState, VerificationState } from "@/types";

type LocaleLabels<T extends string> = Record<T, { en: string; si: string }>;

// TODO(si): conveyancing terminology still needs lawyer mentor review before non-demo use.
export const verificationLabels: LocaleLabels<VerificationState> = {
  unreviewed: { en: "Unreviewed", si: "සමාලෝචනය නොකළ" },
  verified: { en: "Verified", si: "සත්‍යාපිත" },
  corrected: { en: "Corrected", si: "නිවැරදි කළ" },
  conflict: { en: "Conflict", si: "ගැටුම" },
  blocked: { en: "Blocked", si: "අවහිර" },
};
export const processingLabels: LocaleLabels<ProcessingState> = {
  uploaded: { en: "Uploaded", si: "උඩුගත කළා" },
  extracting: { en: "Extracting", si: "නිස්සාරණය කරමින්" },
  "ready-for-review": { en: "Ready for review", si: "සමාලෝචනයට සූදානම්" },
  failed: { en: "Failed", si: "අසාර්ථක" },
  replaced: { en: "Replaced", si: "ප්‍රතිස්ථාපනය කළා" },
};
export const documentRelationLabels: LocaleLabels<DocumentRelation> = {
  authorized: { en: "Authorized", si: "අවසර ලත්" },
  unrelated: { en: "Unrelated", si: "අදාළ නොවන" },
  unclassified: { en: "Unclassified", si: "වර්ගීකරණය නොකළ" },
};
export const identitySideLabels: LocaleLabels<IdentitySide> = {
  front: { en: "Front", si: "ඉදිරිපස" },
  back: { en: "Back", si: "පිටුපස" },
  unknown: { en: "Side unknown", si: "පැත්ත නොදනී" },
};
export const documentKindLabels: LocaleLabels<DocumentKind> = {
  deed: { en: "Deed", si: "ඔප්පුව" },
  "survey-plan": { en: "Survey plan", si: "මිනුම් සැලැස්ම" },
  identity: { en: "Identity", si: "අනන්‍යතාව" },
  assessment: { en: "Assessment", si: "තක්සේරුව" },
  "registry-extract": { en: "Registry extract", si: "ලේඛනාගාර උපුටා ගැනීම" },
  "at-form": { en: "AT form", si: "AT පෝරමය" },
  other: { en: "Other", si: "වෙනත්" },
};
export const matterTypeLabels: LocaleLabels<MatterType> = {
  transfer: { en: "Transfer", si: "මාරුකිරීම" },
  gift: { en: "Gift", si: "දීමනාව" },
  lease: { en: "Lease", si: "බද්ද" },
  mortgage: { en: "Mortgage", si: "උකස" },
  other: { en: "Other", si: "වෙනත්" },
};
export const registrationRegimeLabels: LocaleLabels<RegistrationRegime> = {
  rta: { en: "RTA", si: "RTA" },
  deed: { en: "RDO", si: "RDO" },
  condominium: { en: "Apartment Ownership", si: "මහල් නිවාස හිමිකම" },
  "special-area": { en: "Special Area", si: "විශේෂ කලාපය" },
};
export const checkLabels: LocaleLabels<CheckStatus> = {
  pass: { en: "Pass", si: "සමත්" },
  warning: { en: "Warning", si: "අනතුරු ඇඟවීම" },
  fail: { en: "Fail", si: "අසමත්" },
  "needs-review": { en: "Needs review", si: "සමාලෝචනය අවශ්‍යයි" },
};
export const stepLabels: LocaleLabels<StepState> = {
  "not-started": { en: "Not started", si: "ආරම්භ කර නැත" },
  "in-progress": { en: "In progress", si: "ප්‍රගතියේ" },
  complete: { en: "Complete", si: "සම්පූර්ණ" },
  blocked: { en: "Blocked", si: "අවහිර" },
};
export const authorityTypeLabels: LocaleLabels<AuthorityType> = {
  statute: { en: "Statute", si: "පනත" },
  amendment: { en: "Amendment", si: "සංශෝධනය" },
  gazette: { en: "Gazette", si: "ගැසට්" },
  "case-rule": { en: "Case rule", si: "නඩු නීතිය" },
  "practice-direction": { en: "Practice direction", si: "ප්‍රායෝගික උපදෙස්" },
};
export const courtLevelLabels: LocaleLabels<CourtLevel> = {
  "supreme-court": { en: "Supreme Court", si: "ශ්‍රේෂ්ඨාධිකරණය" },
  "court-of-appeal": { en: "Court of Appeal", si: "අභියාචනාධිකරණය" },
  "high-court": { en: "High Court", si: "මහාධිකරණය" },
  "district-court": { en: "District Court", si: "දිසා අධිකරණය" },
  "not-applicable": { en: "Not applicable", si: "අදාළ නොවේ" },
};
export const authorityWeightLabels: LocaleLabels<AuthorityWeight> = {
  binding: { en: "Binding", si: "බැඳීම් සහිත" },
  persuasive: { en: "Persuasive", si: "ප්‍රබෝධක" },
  historical: { en: "Historical", si: "ඓතිහාසික" },
  "unverified-candidate": { en: "Unverified candidate", si: "සත්‍යාපනය නොකළ අපේක්ෂකයා" },
};
