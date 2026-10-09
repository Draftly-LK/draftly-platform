/**
 * Document-ingestion API calls.
 *
 * Mirrors backend/src/modules/document/api/ingestion_router.py and its request
 * schemas. Source files and detected documents are addressed without their
 * matter in the path (§12.4): the server resolves the row under the caller's
 * `user_id` first and authorises against the matter it turns out to belong to.
 */

import {
  apiFetch,
  apiFetchBlob,
  ifMatch,
  type TokenProvider,
} from "@/lib/api/client";
import type {
  ApiDetectedDocument,
  ApiDocumentReview,
  ApiDocumentInbox,
  ApiProcessingRun,
  ApiSourceFile,
  ApiSourceFileList,
  ApiSourceProcessingStatus,
  ApiReviewCandidate,
} from "@/types/rta";

export interface ListSourceFilesParams {
  limit?: number;
  cursor?: string;
}

export function getDocumentReview(
  getToken: TokenProvider,
  documentId: string,
  generation?: number,
): Promise<ApiDocumentReview> {
  return apiFetch<ApiDocumentReview>(
    `/api/v1/detected-documents/${encodeURIComponent(documentId)}/review${generation === undefined ? "" : `?generation=${generation}`}`,
    { getToken },
  );
}

export function getDetectedDocument(
  getToken: TokenProvider,
  documentId: string,
) {
  return apiFetch<ApiDetectedDocument>(
    `/api/v1/detected-documents/${encodeURIComponent(documentId)}`,
    { getToken },
  );
}

export function refreshDocumentExtraction(
  getToken: TokenProvider,
  documentId: string,
  version: number,
) {
  return apiFetch<ApiDetectedDocument>(
    `/api/v1/detected-documents/${encodeURIComponent(documentId)}/refresh-extraction`,
    {
      method: "POST",
      headers: ifMatch(version),
      getToken,
    },
  );
}

export function getPrivateDocumentArtifact(
  getToken: TokenProvider,
  path: string,
  signal?: AbortSignal,
): Promise<Blob> {
  return apiFetchBlob(path, { getToken, signal });
}

export function editReviewCandidate(
  getToken: TokenProvider,
  candidateId: string,
  value: string,
  version: number,
): Promise<ApiReviewCandidate> {
  return apiFetch<ApiReviewCandidate>(
    `/api/v1/candidate-fields/${encodeURIComponent(candidateId)}`,
    {
      method: "PATCH",
      body: { value },
      headers: ifMatch(version),
      getToken,
    },
  );
}

export function approveReviewCandidate(
  getToken: TokenProvider,
  candidateId: string,
  version: number,
): Promise<ApiReviewCandidate> {
  return apiFetch<ApiReviewCandidate>(
    `/api/v1/candidate-fields/${encodeURIComponent(candidateId)}/approve`,
    { method: "POST", headers: ifMatch(version), getToken },
  );
}

/** Upload one file into a matter. Multipart; the browser sets its own boundary. */
export function uploadSourceFile(
  getToken: TokenProvider,
  matterId: string,
  file: File,
): Promise<ApiSourceFile> {
  const body = new FormData();
  body.append("file", file);
  return apiFetch<ApiSourceFile>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/source-files`,
    {
      method: "POST",
      body,
      getToken,
    },
  );
}

export function listSourceFiles(
  getToken: TokenProvider,
  matterId: string,
  params: ListSourceFilesParams = {},
): Promise<ApiSourceFileList> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.cursor !== undefined) query.set("cursor", params.cursor);
  const search = query.toString();
  const suffix = search ? `?${search}` : "";
  return apiFetch<ApiSourceFileList>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/source-files${suffix}`,
    { getToken },
  );
}

export function getSourceFile(
  getToken: TokenProvider,
  sourceFileId: string,
): Promise<ApiSourceFile> {
  return apiFetch<ApiSourceFile>(
    `/api/v1/source-files/${encodeURIComponent(sourceFileId)}`,
    {
      getToken,
    },
  );
}

/** Current source version and latest persistent outcome; null means no recorded run. */
export function getSourceProcessingStatus(
  getToken: TokenProvider,
  sourceFileId: string,
): Promise<ApiSourceProcessingStatus> {
  return apiFetch<ApiSourceProcessingStatus>(
    `/api/v1/source-files/${encodeURIComponent(sourceFileId)}/processing`,
    { getToken },
  );
}

/**
 * Run the pipeline over one stored file. Synchronous today — the response is a
 * terminal run envelope, not a promise (see `ProcessingRunRead.pollAfterMs`,
 * always null). A "failed" state with `NOT_CONFIGURED` means no OCR provider
 * is wired, not that the request itself went wrong.
 */
export function processSourceFile(
  getToken: TokenProvider,
  sourceFileId: string,
  version: number,
): Promise<ApiProcessingRun> {
  return apiFetch<ApiProcessingRun>(
    `/api/v1/source-files/${encodeURIComponent(sourceFileId)}/process`,
    { method: "POST", headers: ifMatch(version), getToken },
  );
}

export interface SupersedeSourceFileBody {
  supersededBySourceFileId: string;
  /** "SUPERSEDED" (a lawyer decision) or "POSSIBLE_VERSION" (flag without moving state). */
  relationship?: "SUPERSEDED" | "POSSIBLE_VERSION";
  reason?: string;
}

export function supersedeSourceFile(
  getToken: TokenProvider,
  sourceFileId: string,
  body: SupersedeSourceFileBody,
  version: number,
): Promise<ApiSourceFile> {
  return apiFetch<ApiSourceFile>(
    `/api/v1/source-files/${encodeURIComponent(sourceFileId)}/supersede`,
    { method: "POST", body, headers: ifMatch(version), getToken },
  );
}

export interface DocumentInboxParams {
  limit?: number;
  cursor?: string;
}

/** The review queue: files, the documents found in them, and the pairs. */
export function getDocumentInbox(
  getToken: TokenProvider,
  matterId: string,
  params: DocumentInboxParams = {},
): Promise<ApiDocumentInbox> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.cursor !== undefined) query.set("cursor", params.cursor);
  const search = query.toString();
  const suffix = search ? `?${search}` : "";
  return apiFetch<ApiDocumentInbox>(
    `/api/v1/matters/${encodeURIComponent(matterId)}/document-inbox${suffix}`,
    { getToken },
  );
}

export interface FragmentRangeInput {
  sourceFileId: string;
  pageStart: number;
  pageEnd: number;
  orderInDocument?: number;
}

export interface BoundaryDecisionBody {
  fragments: FragmentRangeInput[];
  note?: string;
}

/** Split, join, or reorder the pages a document claims. Source bytes untouched. */
export function recordBoundaryDecision(
  getToken: TokenProvider,
  documentId: string,
  body: BoundaryDecisionBody,
  version: number,
): Promise<ApiDetectedDocument> {
  return apiFetch<ApiDetectedDocument>(
    `/api/v1/detected-documents/${encodeURIComponent(documentId)}/boundary-decisions`,
    { method: "POST", body, headers: ifMatch(version), getToken },
  );
}

export interface ClassificationDecisionBody {
  /** A controlled class id (§12.4) — never free text. */
  classId: string;
  note?: string;
}

/** Confirm or correct the class. Only controlled ids are accepted. */
export function recordClassificationDecision(
  getToken: TokenProvider,
  documentId: string,
  body: ClassificationDecisionBody,
  version: number,
): Promise<ApiDetectedDocument> {
  return apiFetch<ApiDetectedDocument>(
    `/api/v1/detected-documents/${encodeURIComponent(documentId)}/classification-decisions`,
    { method: "POST", body, headers: ifMatch(version), getToken },
  );
}
