import type { JSONContent } from "@tiptap/core";

export type TemplateId =
  | "form-07-amalgamation-subdivision"
  | "form-08-instrument-of-transfer"
  | "form-09-mortgage"
  | "form-10-lease"
  | "form-11-caveat"
  | "form-12-withdrawal-of-caveat"
  | "form-13-power-of-attorney"
  | "form-19-title-certificate"
  | "form-19a-title-certificate"
  | "form-21-condominium"
  | "form-23-agreement-to-sell"
  | "form-24-gift"
  | "form-25-judgment-registration"
  | "form-26-cancellation-of-judgment"
  | "form-27-discharge-of-mortgage"
  | "form-28-relinquishment-life-interest"
  | "form-29-cancellation-of-lease"
  | "form-30-revocation-of-poa"
  | "form-31-registration-of-address"
  | "form-32-partition";

export type TemplateStatus = "ready" | "stub";

export interface TemplateMeta {
  id: TemplateId;
  formNumber: string;
  /** English display title for the catalog */
  titleEn: string;
  /** Sinhala display title for the catalog */
  titleSi: string;
  regime: "rta";
  transactionType: string;
  status: TemplateStatus;
  descriptionEn: string;
}

export interface LegalTemplate {
  meta: TemplateMeta;
  document: JSONContent;
}
