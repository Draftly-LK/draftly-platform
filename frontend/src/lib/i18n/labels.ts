import type { AuthorityType, AuthorityWeight, CheckStatus, CourtLevel, ProcessingState, StepState, VerificationState } from "@/types";

type LocaleLabels<T extends string> = Record<T, { en: string; si: string }>;

// TODO(si): replace English fallbacks after lawyer-reviewed translation.
export const verificationLabels: LocaleLabels<VerificationState> = {
  unreviewed: { en: "Unreviewed", si: "Unreviewed" }, verified: { en: "Verified", si: "Verified" }, corrected: { en: "Corrected", si: "Corrected" }, conflict: { en: "Conflict", si: "Conflict" }, blocked: { en: "Blocked", si: "Blocked" }
};
export const processingLabels: LocaleLabels<ProcessingState> = {
  uploaded: { en: "Uploaded", si: "Uploaded" }, extracting: { en: "Extracting", si: "Extracting" }, "ready-for-review": { en: "Ready for review", si: "Ready for review" }, failed: { en: "Failed", si: "Failed" }, replaced: { en: "Replaced", si: "Replaced" }
};
export const checkLabels: LocaleLabels<CheckStatus> = {
  pass: { en: "Pass", si: "Pass" }, warning: { en: "Warning", si: "Warning" }, fail: { en: "Fail", si: "Fail" }, "needs-review": { en: "Needs review", si: "Needs review" }
};
export const stepLabels: LocaleLabels<StepState> = {
  "not-started": { en: "Not started", si: "Not started" }, "in-progress": { en: "In progress", si: "In progress" }, complete: { en: "Complete", si: "Complete" }, blocked: { en: "Blocked", si: "Blocked" }
};
export const authorityTypeLabels: LocaleLabels<AuthorityType> = {
  statute: { en: "Statute", si: "Statute" }, amendment: { en: "Amendment", si: "Amendment" }, gazette: { en: "Gazette", si: "Gazette" }, "case-rule": { en: "Case rule", si: "Case rule" }, "practice-direction": { en: "Practice direction", si: "Practice direction" }
};
export const courtLevelLabels: LocaleLabels<CourtLevel> = {
  "supreme-court": { en: "Supreme Court", si: "Supreme Court" }, "court-of-appeal": { en: "Court of Appeal", si: "Court of Appeal" }, "high-court": { en: "High Court", si: "High Court" }, "district-court": { en: "District Court", si: "District Court" }, "not-applicable": { en: "Not applicable", si: "Not applicable" }
};
export const authorityWeightLabels: LocaleLabels<AuthorityWeight> = {
  binding: { en: "Binding", si: "Binding" }, persuasive: { en: "Persuasive", si: "Persuasive" }, historical: { en: "Historical", si: "Historical" }, "unverified-candidate": { en: "Unverified candidate", si: "Unverified candidate" }
};

