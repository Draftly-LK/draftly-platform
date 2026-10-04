/**
 * Typed fetch wrapper for the Draftly FastAPI backend.
 *
 * This is the only place in the frontend that calls `fetch` against FastAPI.
 * Screens go through the typed helpers in `lib/api/*`, never through fetch
 * directly, so token handling and the error envelope stay in one place.
 *
 * The client is deliberately opt-in: when `NEXT_PUBLIC_API_BASE_URL` is unset
 * the app keeps running on the `lib/data.ts` mocks. That preserves the
 * deterministic offline demo required by the build conventions.
 */

/** Shape of `ErrorDetail` in backend/src/platform/errors.py. */
interface WireErrorDetail {
  code?: string;
  message?: string;
  details?: Record<string, unknown>;
  /** snake_case on the wire — ErrorDetail has no alias generator. */
  correlation_id?: string;
}

interface WireErrorEnvelope {
  error?: WireErrorDetail;
}

/**
 * A structured backend failure.
 *
 * `code` mirrors the backend's stable error codes (`unauthenticated`,
 * `capability_denied`, `step_up_required`, …) so callers branch on the code
 * rather than on human-readable message text.
 */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly correlationId: string;
  readonly details: Record<string, unknown>;

  constructor(
    status: number,
    code: string,
    message: string,
    correlationId: string,
    details: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
    this.details = details;
  }
}

/** Supplies a Clerk session JWT, or null when signed out. */
export type TokenProvider = () => Promise<string | null>;

/**
 * The version segment every route lives under (`api-conventions.md` §1).
 *
 * The canonical split in this frontend: **the base URL is the bare origin and
 * every endpoint path carries the prefix.** `NEXT_PUBLIC_API_BASE_URL` is
 * therefore `http://localhost:8000`, not `http://localhost:8000/api/v1`.
 *
 * A base that also carried the prefix would repeat the version segment twice
 * in every URL, so a prefix accidentally left on the env var is stripped here
 * rather than silently doubled at every call site.
 */
export const API_VERSION_PREFIX = "/api/v1";

export function apiBaseUrl(): string | null {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!raw) return null;
  const trimmed = raw.replace(/\/+$/, "");
  return trimmed.endsWith(API_VERSION_PREFIX)
    ? trimmed.slice(0, -API_VERSION_PREFIX.length).replace(/\/+$/, "")
    : trimmed;
}

/**
 * True when the backend is configured. Screens use this to decide between
 * live data and mocks; it is never a security check.
 */
export function isApiEnabled(): boolean {
  return apiBaseUrl() !== null;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** A `FormData` body is sent as-is (multipart); anything else is JSON-encoded. */
  body?: unknown;
  getToken: TokenProvider;
  /**
   * Extra request headers, merged after the ones this client owns.
   *
   * Used for conditional requests: the matter routes take optimistic
   * concurrency as `If-Match: "<version>"` (see `require_if_match` in
   * backend/src/api/deps.py), never as a body field.
   */
  headers?: Record<string, string>;
  /**
   * Second, freshly re-authenticated token for legally significant actions.
   * Sent as `X-Step-Up-Token`; see `require_step_up` in auth_service.py.
   */
  stepUpToken?: string;
  signal?: AbortSignal;
}

/**
 * `If-Match: "<version>"` for a conditional request (api-conventions §3). A
 * missing header is 428 and a stale one is 412. Shared by every module's
 * accessor file so the quoting rule lives in exactly one place.
 */
export function ifMatch(version: number): Record<string, string> {
  return { "If-Match": `"${version}"` };
}

async function toApiError(response: Response): Promise<ApiError> {
  let envelope: WireErrorEnvelope = {};
  try {
    envelope = (await response.json()) as WireErrorEnvelope;
  } catch {
    // Non-JSON failure (proxy error, connection reset). Fall through to the
    // generic message below rather than masking the status code.
  }
  const detail = envelope.error ?? {};
  return new ApiError(
    response.status,
    detail.code ?? "unknown_error",
    detail.message ?? `Request failed with status ${response.status}.`,
    detail.correlation_id ?? "",
    detail.details ?? {},
  );
}

/**
 * Perform an authenticated request against the backend.
 *
 * Throws `ApiError` on any non-2xx response so callers handle one error type.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestOptions,
): Promise<T> {
  const baseUrl = apiBaseUrl();
  if (baseUrl === null) {
    throw new ApiError(
      0,
      "api_not_configured",
      "NEXT_PUBLIC_API_BASE_URL is not set; the backend is unavailable.",
      "",
      {},
    );
  }

  const token = await options.getToken();
  if (!token) {
    throw new ApiError(401, "unauthenticated", "No active session.", "", {});
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };
  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;
  if (options.body !== undefined && !isFormData) {
    // Left unset for FormData: the browser must set its own multipart
    // boundary, which it can only do if this client does not pre-empt it.
    headers["Content-Type"] = "application/json";
  }
  if (options.stepUpToken) {
    headers["X-Step-Up-Token"] = options.stepUpToken;
  }
  if (options.headers) {
    Object.assign(headers, options.headers);
  }

  const response = await fetch(`${baseUrl}${path}`, {
    method: options.method ?? "GET",
    headers,
    body:
      options.body === undefined
        ? undefined
        : isFormData
          ? (options.body as FormData)
          : JSON.stringify(options.body),
    signal: options.signal,
  });

  if (!response.ok) {
    throw await toApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** Authenticated binary read for private document derivatives. */
export async function apiFetchBlob(
  path: string,
  options: RequestOptions,
): Promise<Blob> {
  const baseUrl = apiBaseUrl();
  if (baseUrl === null) {
    throw new ApiError(
      0,
      "api_not_configured",
      "The backend is unavailable.",
      "",
      {},
    );
  }
  const token = await options.getToken();
  if (!token)
    throw new ApiError(401, "unauthenticated", "No active session.", "", {});
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal: options.signal,
  });
  if (!response.ok) throw await toApiError(response);
  return response.blob();
}

/**
 * Text to show for a failed request. A missing backend configuration is a
 * deployment detail (it names an environment variable), so users get the
 * caller's translated fallback instead; other API errors keep the server's
 * message.
 */
export function apiErrorMessage(cause: unknown, fallback: string): string {
  if (!(cause instanceof ApiError)) return fallback;
  return cause.code === "api_not_configured" ? fallback : cause.message;
}
