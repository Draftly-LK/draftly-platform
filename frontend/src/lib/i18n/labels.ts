import type { AuthorityType, AuthorityWeight, CheckStatus, CourtLevel, PhysicalOriginalStatus, SourceFileState, StepState, VerificationState } from "@/types";

type LocaleLabels<T extends string> = Record<T, { en: string; si: string }>;

// TODO(si): replace English fallbacks after lawyer-reviewed translation.
export const verificationLabels: LocaleLabels<VerificationState> = {
  unreviewed: { en: "Unreviewed", si: "Unreviewed" }, verified: { en: "Verified", si: "Verified" }, corrected: { en: "Corrected", si: "Corrected" }, conflict: { en: "Conflict", si: "Conflict" }, blocked: { en: "Blocked", si: "Blocked" }
};
/** §10.2 source-file states. Wording states what the server did, not a guess. */
export const sourceFileStateLabels: LocaleLabels<SourceFileState> = {
  UPLOAD_INITIATED: { en: "Upload started", si: "Upload started" }, QUARANTINED: { en: "In quarantine", si: "In quarantine" }, VALIDATED: { en: "Validated", si: "Validated" }, STORED: { en: "Stored", si: "Stored" }, PROCESSING: { en: "Processing", si: "Processing" }, PROCESSED: { en: "Processed", si: "Processed" }, PROCESSING_FAILED: { en: "Processing failed", si: "Processing failed" }, REJECTED: { en: "Rejected", si: "Rejected" }, SUPERSEDED: { en: "Superseded", si: "Superseded" }
};
/** §5.4 physical-original dimension. `ORIGINAL_INSPECTED` is human-only. */
export const physicalOriginalLabels: LocaleLabels<PhysicalOriginalStatus> = {
  NOT_REQUIRED: { en: "Original not required", si: "Original not required" }, UNKNOWN: { en: "Original status unknown", si: "Original status unknown" }, COPY_ONLY: { en: "Copy only", si: "Copy only" }, ORIGINAL_REPORTED: { en: "Original reported", si: "Original reported" }, ORIGINAL_INSPECTED: { en: "Original inspected", si: "Original inspected" }
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

