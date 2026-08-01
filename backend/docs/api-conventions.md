# API conventions

Companion to `backend/backend-implementation-plan-v0.md` §7 and every service
design under `docs/services/`. Rules here apply to every `/api/v1` route unless
a service doc names an explicit, justified exception.

Written because pagination appeared in five of twenty service docs, optimistic
concurrency was a domain concept in eight with no wire format in any, and three
docs independently "leaned" a different way on the same path-prefix mismatch.

## 1. Paths and versioning

- Every route is under `/api/v1`. The version changes only for a breaking change
  to an existing resource, never to add one.
- The deployed frontend calls `/api/…` without the version segment. The frontend
  API client sets the base URL to `/api/v1`; route paths in frontend code drop
  the prefix. No server-side alias is added, and no service doc re-litigates
  this.
- Resource paths are plural and matter-scoped where the resource belongs to a
  matter: `/api/v1/matters/{matterId}/documents`.
- Where plan §7 and the frontend disagree on scoping (approval and export), the
  **matter-scoped route is the public contract** and the server resolves it to
  the version or approval that is actually pinned:

  | Public route | Resolves to |
  | --- | --- |
  | `POST /matters/{id}/drafts/{draftId}/submit` | the draft's active version |
  | `POST /matters/{id}/drafts/{draftId}/approve` | the draft's `in-review` version |
  | `POST /matters/{id}/drafts/{draftId}/exports` | the draft's current Approval |

## 2. Pagination

Every list endpoint is paginated. There are no unbounded arrays, including the
audit global feed, the fact list, the draft list, the obligation list, and the
notification list.

Request: `?limit=<1..100, default 50>&cursor=<opaque>`, plus resource-specific
filters.

Response:

```json
{
  "items": [],
  "page": { "nextCursor": "eyJ...", "hasMore": true, "limit": 50 }
}
```

- Cursors are opaque, signed, and encode the sort key plus the tie-breaker id.
  Offset pagination is not used; it double-counts under concurrent writes.
- Default sort is `createdAt` descending with `id` as the tie-breaker, unless the
  service doc states otherwise.
- Total counts are not returned by default. A count is a separate, explicitly
  requested, and separately cached call.

## 3. Optimistic concurrency

Every mutable aggregate carries an integer `version` column. The wire format is
HTTP conditional requests, not a body field:

```http
PATCH /api/v1/matters/m-123
If-Match: "7"
```

- The `ETag` on any single-resource `GET` is the quoted `version`.
- A mutating request against a versioned aggregate **must** send `If-Match`.
  A missing header is `428 Precondition Required`; a stale value is
  `412 Precondition Failed` with the current version in the response `ETag`.
- Immutable resources (a `DocumentVersion`, a `DraftVersion`, an `Approval`, an
  `AuditEvent`) have no version and reject `If-Match`.
- Domain layers keep taking `expected_version` as a parameter; the router
  translates the header.

## 4. Idempotency

Two different mechanisms, often confused:

| Mechanism | Used for | Key |
| --- | --- | --- |
| `Idempotency-Key` request header | Client-initiated POSTs that create something | Client-generated UUID, unique per logical attempt |
| Registry `idempotencyKey` | Event consumers and worker jobs | Derived from the aggregate and version (`events.md` §2) |

`Idempotency-Key` is **required** on `POST /matters`, `POST
/matters/{id}/documents`, `POST /documents/{id}/versions`, `POST
/matters/{id}/drafts`, `POST …/versions`, `POST …/exports`, `POST
/obligations`, `POST /billing/checkout`, and `POST
/transcriptions/sessions`. The server stores `(organisation_id, route, key)` →
response for 24 hours and replays the stored response for a repeat. A repeat
with a *different* body under the same key is `409 Conflict`.

Provider webhooks use the provider's event id instead, with a documented
deterministic fallback (`billing-service.md` §5.4).

## 5. Errors

One envelope, on every non-2xx response:

```json
{
  "error": {
    "code": "capability_denied",
    "message": "This action requires the draft.approve capability.",
    "details": {},
    "correlationId": "corr-01K2..."
  }
}
```

- `code` is a stable, machine-readable snake_case identifier from a closed
  catalogue in `domain/errors.py`. The frontend switches on `code`, never on
  `message`.
- `message` is safe to display. It never contains a raw client value, a storage
  path, a provider response, a stack frame, or a SQL fragment.
- `details` is typed per `code` — for example `{"missingFactKeys": ["extent"]}`
  for `draft_eligibility_unmet`, `{"capability": "draft.approve"}` for
  `capability_denied`.
- `correlationId` is echoed on every error so a user can quote it in support.

Status mapping:

| Status | Meaning |
| --- | --- |
| 400 | Malformed request or failed schema validation |
| 401 | No valid identity |
| 403 | Member of the resource, capability denied (`security-model.md` §5) |
| 404 | Resource absent **or** caller not a member — indistinguishable |
| 409 | Idempotency-key conflict, or a state conflict such as a duplicate approval |
| 412 / 428 | Optimistic concurrency (§3) |
| 422 | Domain rule refused a well-formed request (blocked gate, illegal transition) |
| 429 | Rate limit or quota exhausted — body names the metric |
| 503 | Dependency unavailable and the operation fails closed |

A domain error is never a 500. An illegal state transition raised by the domain
layer maps to 422 with the transition in `details`.

**A 2xx never implies a legal conclusion.** Plan §8 requires this explicitly:
a successful response to `verify` means the decision was recorded, not that the
fact is correct.

## 6. Long-running work

Any operation that runs OCR, retrieval, rendering, or transcription returns a
job immediately and never holds the request open:

```json
{ "jobId": "job-...", "state": "queued", "pollAfterMs": 1500 }
```

- `GET /api/v1/jobs/{jobId}` returns `{state, progress?, result?, error?}` with
  states `queued | running | succeeded | failed | dead_letter`.
- Services with a natural resource for the result (`GET /exports/{id}`,
  `GET /documents/{id}/processing`) expose that too; both read the same row.
- Streaming, where offered, is resumable server-sent events keyed by
  `Last-Event-ID` (`research-service.md` §2.2). A stream is presentation
  state — the persisted result is authoritative.

## 7. Request context headers

| Header | Direction | Rule |
| --- | --- | --- |
| `Authorization: Bearer` | in | Validated by `IdentityPort`; never logged |
| `X-Draftly-Organisation` | in | Selects which membership to verify; never establishes one |
| `Idempotency-Key` | in | §4 |
| `If-Match` | in | §3 |
| `X-Correlation-Id` | in, optional | Accepted from the client, regenerated if absent, echoed on the response and attached to every audit row and event |
| `ETag` | out | Current aggregate version |
| `Retry-After` | out | On 429 and 503 |

## 8. Rate limiting

Per organisation and per route class, not per IP: `read`, `write`,
`expensive` (upload, ask, export, transcription), and `webhook`. Exceeding a
limit is 429 with `Retry-After`; exceeding a **plan quota** is also 429 but with
`code: "quota_exhausted"` and the metric in `details`, so the frontend can offer
an upgrade rather than a retry.

## 9. Schema and contract discipline

- Pydantic models in `schemas/` are the wire contract. Domain objects are never
  serialised directly.
- OpenAPI is generated on every build and committed as
  `backend/contracts/openapi.v1.json`. A diff that removes or renames a field
  fails CI unless the change is accompanied by a version bump or an entry in
  `frontend-contract-migration.md`.
- Contract fixtures under `tests/contract/fixtures/` are shared with the
  frontend and are the only sanctioned source of example payloads.
- Every response field that is a legal state (`verificationState`,
  `approvalState`, `status`, `verdict`) is a closed enum, never a free string.
