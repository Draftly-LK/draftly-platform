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

export function apiBaseUrl(): string | null {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!raw) return null;
  return raw.replace(/\/+$/, "");
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
export async function apiFetch<T>(path: string, options: RequestOptions): Promise<T> {
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
  if (options.body !== undefined) {
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
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
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
