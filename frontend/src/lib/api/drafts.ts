/**
 * Form-drafting API calls.
 *
 * Mirrors backend/src/modules/draft/api/router.py and its request schemas.
 * Generation and preflight are synchronous — nothing here rasterizes, extracts,
 * or renders. Forms are addressed without their matter in the path (§12.4).
 *
 * A 2xx from any of these routes means a record was written, never that the
 * draft may be executed or registered: `preflight.registrationReady` is false
 * for every form in this repository (§9.5).
 */

import { apiFetch, ifMatch, type TokenProvider } from "@/lib/api/client";
import type { ApiGeneratedForm, ApiGeneratedFormList } from "@/types/rta";

export interface GenerateFormBody {
  /** Selects between the templates the confirmed subtype already permits. */
  templateId?: string;
}

/**
 * Generate a working draft from the confirmed subtype and the fact tier. The
 * subtype must already be lawyer-confirmed — it is read server-side, never
 * from this body.
 */
export function generateForm(
  getToken: TokenProvider,
  matterId: string,
  body: GenerateFormBody = {},
): Promise<ApiGeneratedForm> {
  return apiFetch<ApiGeneratedForm>(`/api/v1/matters/${encodeURIComponent(matterId)}/forms`, {
    method: "POST",
    body,
    getToken,
  });
}

export interface ListFormsParams {
  limit?: number;
  cursor?: string;
}

/** Every form version on the matter, newest first. Nothing is ever deleted. */
export function listForms(
  getToken: TokenProvider,
  matterId: string,
  params: ListFormsParams = {},
): Promise<ApiGeneratedFormList> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.cursor !== undefined) query.set("cursor", params.cursor);
  const search = query.toString();
  const suffix = search ? `?${search}` : "";
  return apiFetch<ApiGeneratedFormList>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/forms${suffix}`,
    { getToken },
  );
}

/** The whole binding record, with a freshly evaluated preflight beside it. */
export function getForm(getToken: TokenProvider, formId: string): Promise<ApiGeneratedForm> {
  return apiFetch<ApiGeneratedForm>(`/api/v1/forms/${encodeURIComponent(formId)}`, { getToken });
}

export interface FieldDecisionBody {
  fieldId: string;
  /** "CONFIRM" | "CORRECT" | "CLEAR". A critical field is never corrected here. */
  action: "CONFIRM" | "CORRECT" | "CLEAR";
  /** Only read for CORRECT, and only where the template permits lawyer-authored text. */
  value?: string;
  reason?: string;
}

/** Confirm, correct, or clear one field binding. */
export function recordFieldDecision(
  getToken: TokenProvider,
  formId: string,
  body: FieldDecisionBody,
  version: number,
): Promise<ApiGeneratedForm> {
  return apiFetch<ApiGeneratedForm>(`/api/v1/forms/${encodeURIComponent(formId)}/field-decisions`, {
    method: "POST",
    body,
    headers: ifMatch(version),
    getToken,
  });
}

/**
 * Run the deterministic gate report over all four sources plus the template.
 * A POST because the run is an audit event, not a state change: the report
 * never advances the form on its own.
 */
export function runPreflight(getToken: TokenProvider, formId: string): Promise<ApiGeneratedForm> {
  return apiFetch<ApiGeneratedForm>(`/api/v1/forms/${encodeURIComponent(formId)}/preflight`, {
    method: "POST",
    getToken,
  });
}

export interface MarkStaleBody {
  reason?: string;
}

/**
 * Re-evaluate the form against its current inputs (§9.5, §10.5, §10.7). An
 * approved form is never rewritten; amending it is a new form version.
 */
export function markFormStale(
  getToken: TokenProvider,
  formId: string,
  body: MarkStaleBody,
  version: number,
): Promise<ApiGeneratedForm> {
  return apiFetch<ApiGeneratedForm>(`/api/v1/forms/${encodeURIComponent(formId)}/mark-stale`, {
    method: "POST",
    body,
    headers: ifMatch(version),
    getToken,
  });
}
