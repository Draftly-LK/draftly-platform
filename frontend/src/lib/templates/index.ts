import type { LegalTemplate, TemplateId } from "./types";
import { form07Document } from "./form-07-amalgamation-subdivision/document";
import { form07Meta } from "./form-07-amalgamation-subdivision/meta";
import { form08Document } from "./form-08-instrument-of-transfer/document";
import { form08Meta } from "./form-08-instrument-of-transfer/meta";
import { form09Document } from "./form-09-mortgage/document";
import { form09Meta } from "./form-09-mortgage/meta";
import { form10Document } from "./form-10-lease/document";
import { form10Meta } from "./form-10-lease/meta";
import { form11Document } from "./form-11-caveat/document";
import { form11Meta } from "./form-11-caveat/meta";
import { form12Document } from "./form-12-withdrawal-of-caveat/document";
import { form12Meta } from "./form-12-withdrawal-of-caveat/meta";
import { form13Document } from "./form-13-power-of-attorney/document";
import { form13Meta } from "./form-13-power-of-attorney/meta";
import { form19Document } from "./form-19-title-certificate/document";
import { form19Meta } from "./form-19-title-certificate/meta";
import { form19aDocument } from "./form-19a-title-certificate/document";
import { form19aMeta } from "./form-19a-title-certificate/meta";
import { form21Document } from "./form-21-condominium/document";
import { form21Meta } from "./form-21-condominium/meta";
import { form23Document } from "./form-23-agreement-to-sell/document";
import { form23Meta } from "./form-23-agreement-to-sell/meta";
import { form24Document } from "./form-24-gift/document";
import { form24Meta } from "./form-24-gift/meta";
import { form25Document } from "./form-25-judgment-registration/document";
import { form25Meta } from "./form-25-judgment-registration/meta";
import { form26Document } from "./form-26-cancellation-of-judgment/document";
import { form26Meta } from "./form-26-cancellation-of-judgment/meta";
import { form27Document } from "./form-27-discharge-of-mortgage/document";
import { form27Meta } from "./form-27-discharge-of-mortgage/meta";
import { form28Document } from "./form-28-relinquishment-life-interest/document";
import { form28Meta } from "./form-28-relinquishment-life-interest/meta";
import { form29Document } from "./form-29-cancellation-of-lease/document";
import { form29Meta } from "./form-29-cancellation-of-lease/meta";
import { form30Document } from "./form-30-revocation-of-poa/document";
import { form30Meta } from "./form-30-revocation-of-poa/meta";
import { form31Document } from "./form-31-registration-of-address/document";
import { form31Meta } from "./form-31-registration-of-address/meta";
import { form32Document } from "./form-32-partition/document";
import { form32Meta } from "./form-32-partition/meta";

export type {
  LegalTemplate,
  TemplateId,
  TemplateMeta,
  TemplateStatus,
} from "./types";

export const legalTemplates: LegalTemplate[] = [
  { meta: form07Meta, document: form07Document },
  { meta: form08Meta, document: form08Document },
  { meta: form09Meta, document: form09Document },
  { meta: form10Meta, document: form10Document },
  { meta: form11Meta, document: form11Document },
  { meta: form12Meta, document: form12Document },
  { meta: form13Meta, document: form13Document },
  { meta: form19Meta, document: form19Document },
  { meta: form19aMeta, document: form19aDocument },
  { meta: form21Meta, document: form21Document },
  { meta: form23Meta, document: form23Document },
  { meta: form24Meta, document: form24Document },
  { meta: form25Meta, document: form25Document },
  { meta: form26Meta, document: form26Document },
  { meta: form27Meta, document: form27Document },
  { meta: form28Meta, document: form28Document },
  { meta: form29Meta, document: form29Document },
  { meta: form30Meta, document: form30Document },
  { meta: form31Meta, document: form31Document },
  { meta: form32Meta, document: form32Document },
];

export function listTemplates(): LegalTemplate[] {
  return legalTemplates;
}

export function getTemplate(id: string): LegalTemplate | undefined {
  return legalTemplates.find((template) => template.meta.id === id);
}

export function isTemplateId(id: string): id is TemplateId {
  return legalTemplates.some((template) => template.meta.id === id);
}
