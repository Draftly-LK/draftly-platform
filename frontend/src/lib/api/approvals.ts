/**
 * Approval, export, and registration API calls.
 *
 * Mirrors backend/src/modules/approval/api/router.py and its request schemas.
 * No route here takes `If-Match`: an approval, an export, and a registration
 * event are all immutable records with no version to condition on (§9.6).
 *
 * A 2xx here is never a legal conclusion. A 201 from `createExport` means a
 * record was written, not that the instrument may be executed, presented, or
 * registered. A 201 from `createRegistrationEvent` means the lawyer's account
 * of an official act was recorded, not that the act occurred.
 */

import { apiFetch, type TokenProvider } from "@/lib/api/client";
import type {
  ApiApprovalCreated,
  ApiApprovalList,
  ApiFormExport,
  ApiFormExportList,
  ApiRegistrationEventCreated,
  ApiRegistrationEventList,
  ExportFormat,
  RegistrationEventType,
} from "@/types/rta";

export interface ApproveFormBody {
  /** Must name exactly the warnings the server computed on the current preflight. */
  disposedWarningIds?: string[];
  declarationVersion?: string;
}

/** Approve one exact form snapshot. Responsible lawyer only (§12.5). */
export function createApproval(
  getToken: TokenProvider,
  formId: string,
  body: ApproveFormBody = {},
): Promise<ApiApprovalCreated> {
  return apiFetch<ApiApprovalCreated>(`/api/v1/forms/${encodeURIComponent(formId)}/approvals`, {
    method: "POST",
    body,
    getToken,
  });
}

export interface ListParams {
  limit?: number;
  cursor?: string;
}

/** The approval history of one form. Revoked approvals are included. */
export function listApprovals(
  getToken: TokenProvider,
  formId: string,
  params: ListParams = {},
): Promise<ApiApprovalList> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.cursor !== undefined) query.set("cursor", params.cursor);
  const search = query.toString();
  const suffix = search ? `?${search}` : "";
  return apiFetch<ApiApprovalList>(`/api/v1/forms/${encodeURIComponent(formId)}/approvals${suffix}`, {
    getToken,
  });
}

export interface ExportFormBody {
  format: ExportFormat;
}

/**
 * Produce one export record. No document is produced — every template here is
 * a transcription with no approved production rendering (§9.5), so the result
 * is a manifest, explicitly an internal-review artifact.
 */
export function createExport(
  getToken: TokenProvider,
  formId: string,
  body: ExportFormBody,
): Promise<ApiFormExport> {
  return apiFetch<ApiFormExport>(`/api/v1/forms/${encodeURIComponent(formId)}/exports`, {
    method: "POST",
    body,
    getToken,
  });
}

/** Every export taken on the matter, newest first. Nothing is ever deleted. */
export function listExports(
  getToken: TokenProvider,
  matterId: string,
  params: ListParams = {},
): Promise<ApiFormExportList> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.cursor !== undefined) query.set("cursor", params.cursor);
  const search = query.toString();
  const suffix = search ? `?${search}` : "";
  return apiFetch<ApiFormExportList>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/exports${suffix}`,
    { getToken },
  );
}

export interface RecordRegistrationEventBody {
  eventType: RegistrationEventType;
  /** ISO calendar date, e.g. "2026-08-16". A day, not an instant. */
  eventDate: string;
  evidenceReferenceIds?: string[];
  generatedFormId?: string;
  dayBookReference?: string;
  registryOffice?: string;
  resultNote?: string;
}

/**
 * Record an attestation, a presentation, or a registry result. Only a
 * recorded registration result reaches `REGISTERED` (§9.6, §10.1, §17); a
 * confirmed attestation date starts the s. 45(1) seven-working-day task.
 */
export function createRegistrationEvent(
  getToken: TokenProvider,
  matterId: string,
  body: RecordRegistrationEventBody,
): Promise<ApiRegistrationEventCreated> {
  return apiFetch<ApiRegistrationEventCreated>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/registration-events`,
    { method: "POST", body, getToken },
  );
}

/** Every recorded registry act on the matter, newest first. */
export function listRegistrationEvents(
  getToken: TokenProvider,
  matterId: string,
  params: ListParams = {},
): Promise<ApiRegistrationEventList> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.cursor !== undefined) query.set("cursor", params.cursor);
  const search = query.toString();
  const suffix = search ? `?${search}` : "";
  return apiFetch<ApiRegistrationEventList>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/registration-events${suffix}`,
    { getToken },
  );
}
