# Storage service V0 implementation plan

Status: proposed; implementation requires approval.

Companion to:

- `backend/backend-implementation-plan-v0.md`;
- `backend/docs/infrastructure.md`;
- `backend/docs/services/storage-service.md`;
- `backend/docs/services/document-service.md`; and
- `backend/docs/services/audit-service.md`.

## 1. Goal

Implement the first provider-neutral version of Draftly's `storage_service` and
prove this synthetic-data path:

```text
document_service
  -> reserve upload
  -> generate a generation-safe GCS V4 PUT URL
  -> upload the object
  -> finalise and verify the exact object generation
  -> issue a generation-pinned GCS V4 GET URL
```

The initial implementation will also provide a filesystem adapter for local
development and contract testing.

The implementation will not add a public storage router. The future document
API will authorize the caller and then invoke `ObjectStoragePort` internally.

## 2. Current repository state

The backend currently provides the Phase 0 application factory, settings,
health endpoints, safe API errors, structured logging, module directories, and
CI quality gates.

The following foundations do not exist yet:

- a database engine or session factory;
- SQLAlchemy models;
- an Alembic environment or migrations;
- a server-built request-context type;
- an implemented `document_service`;
- a durable audit port or audit repository; and
- storage domain, application, repository, or provider code.

The implementation must establish the shared database primitives without
creating a second database framework inside the storage module.

At the time this plan was written, the working tree also contained:

- an uncommitted database schema addition to `storage-service.md`;
- uncommitted SQLAlchemy, Alembic, psycopg, Google Auth, and GCS dependency
  additions in `pyproject.toml` and `uv.lock`; and
- an untracked, empty `backend/.env.example`.

These changes must be reviewed and incorporated deliberately. They are not a
completed storage implementation.

## 3. Infrastructure already available

The staging GCS resources are already configured:

| Resource | Value |
| --- | --- |
| GCP project | `draftly-502319` |
| Bucket | `draftly-502319-staging-storage` |
| Region | `asia-southeast1` |
| Storage class | Standard |
| Uniform bucket-level access | enabled |
| Public access prevention | enabled |
| Object versioning | enabled |
| Encryption | Google-managed |
| Runtime/signing service account | `draftly-storage-staging@draftly-502319.iam.gserviceaccount.com` |
| Real client data | not approved |

The service account has bucket-level Storage Object User access and the needed
Service Account Token Creator permission. IAM Service Account Credentials is
enabled. No service-account JSON key exists or will be required.

Cloud Run, application secrets, and bucket CORS remain unconfigured.

## 4. Delivery strategy

Implementation should be divided into two pull requests.

### PR 1: database and request-context foundation

- Shared SQLAlchemy and psycopg session infrastructure.
- Typed database settings.
- Server-built request context.
- Alembic configuration.
- Storage ORM models and initial migration.
- PostgreSQL migration and repository tests.
- Disposable PostgreSQL in backend CI.

This PR makes no GCS calls.

### PR 2: working storage path

- Storage domain models and typed errors.
- Public and provider-facing ports.
- Storage repository implementation.
- Application service flows.
- Filesystem and GCS adapters.
- Safe audit boundary and test recorder.
- Configuration examples, CORS example, and Cloud Run instructions.
- Unit, contract, integration, and security tests.

## 5. Shared database foundation

Add shared database code under `src/platform/db/`, not inside
`modules/storage/`.

The foundation will provide:

- a shared SQLAlchemy declarative base;
- async SQLAlchemy sessions using psycopg;
- a bounded connection pool;
- a transaction/unit-of-work boundary;
- a pooled runtime database URL; and
- a direct migration URL for Alembic.

Database URLs must use secret-aware settings and must never appear in object
representations, logs, readiness details, or error responses.

The application remains bootable without database or storage configuration so
`/health/live` continues to work without external infrastructure. When storage
is explicitly enabled, its complete configuration is validated and its safe
dependency state is included in `/health/ready`.

Provider operations use async ports. Synchronous Google and filesystem SDK
operations run through `asyncio.to_thread` so they do not block FastAPI's event
loop.

## 6. Request context

Add a server-owned `RequestContext` to the platform layer containing:

- actor ID;
- organisation ID;
- correlation ID; and
- the matter IDs available to the current operation.

The initial storage module performs defence-in-depth scope checks against this
context. It does not implement authentication, roles, capabilities, or matter
membership itself.

Every storage repository method accepts an organisation ID. A matter-scoped
method also accepts a matter ID. No repository method may load an object or
reservation using only its object ID.

Cross-organisation and cross-matter requests return the same typed not-found
error as a missing record.

## 7. Database migration

Create an Alembic environment under the existing `backend/migrations/`
directory. Runtime traffic uses `DRAFTLY_DATABASE_URL`; migrations use
`DRAFTLY_DATABASE_MIGRATION_URL`.

Use named PostgreSQL check constraints over `text` lifecycle columns rather
than native PostgreSQL enums. This keeps rollback and future controlled state
additions straightforward.

### 7.1 `storage_objects`

Create the columns documented in `storage-service.md`:

- `id`;
- `organisation_id`;
- `matter_id`;
- `owner_service`;
- `owner_type`;
- `owner_id`;
- `object_class`;
- `provider`;
- `bucket_ref`;
- `object_key`;
- `provider_generation`;
- `sha256`;
- `provider_checksum`;
- `size_bytes`;
- `media_type`;
- `state`;
- `deletion_command_id`;
- `row_version`;
- `created_at`;
- `finalised_at`; and
- `deleted_at`.

Constraints and indexes:

- UUID primary key;
- non-null organisation ID;
- matter ID required for all initial non-corpus objects;
- valid object class, provider, and state checks;
- lowercase 64-character hexadecimal SHA-256 when present;
- non-negative verified size;
- finalisation metadata required for `available` objects;
- unique `(provider, bucket_ref, object_key)` to enforce write-once keys;
- owner lookup index covering organisation, matter, owner service, owner type,
  and owner ID;
- reconciliation index covering organisation, state, and creation time; and
- `row_version >= 1` with SQLAlchemy optimistic concurrency enabled.

There are no database foreign keys to matter, document, export, retention, or
identity tables because those tables belong to other services.

### 7.2 `storage_upload_reservations`

Create:

- `id`;
- `organisation_id`;
- `matter_id`;
- `storage_object_id`;
- `upload_method`;
- `expected_size_bytes`;
- `allowed_media_types`;
- `expected_sha256`;
- `state`;
- `expires_at`;
- `created_by`;
- `row_version`;
- `created_at`; and
- `finalised_at`.

Constraints and indexes:

- UUID primary key;
- non-null organisation ID;
- unique storage-object ID;
- restricted-delete foreign key to `storage_objects.id`;
- upload method restricted to `PUT` in V0;
- strictly positive expected size;
- non-empty PostgreSQL media-type array;
- lowercase 64-character hexadecimal expected SHA-256 when present;
- valid reservation state;
- organisation/state/expiry index; and
- `row_version >= 1` with optimistic concurrency enabled.

The repository validates equal organisation and matter scope on both linked
rows before finalisation.

## 8. Storage domain

Create closed enums for:

- providers: `filesystem`, `gcs`;
- object classes: `original`, `derivative`, `export`, `voice`, `corpus`;
- all six documented object states;
- all four documented reservation states; and
- data classification: `synthetic`, `real`.

Create provider-neutral value objects for:

- record scope;
- owning service, type, and aggregate ID;
- document and document-version target IDs;
- upload constraints;
- stored-object metadata;
- reservation metadata;
- upload grants;
- download grants; and
- safe audit metadata.

Signed URLs are sensitive bearer credentials. Their value fields must be
excluded from representations and must never be accepted by an audit method.

## 9. Typed storage errors

The storage domain will define errors for:

- hidden or missing records;
- invalid scope;
- invalid configuration;
- upload size refusal;
- media-type refusal;
- expired reservation;
- finalised or replayed reservation;
- conditional-write conflict;
- unavailable object state;
- checksum or integrity failure;
- retryable provider failure; and
- permanent provider failure.

SQLAlchemy and Google Cloud exceptions are translated at infrastructure
boundaries. Raw SQL, provider messages, bucket names, keys, and URLs never enter
the public error envelope.

## 10. Ports

### 10.1 `ObjectStoragePort`

Expose async provider-neutral operations:

```text
reserve_upload
finalise_upload
open_stream
issue_download_grant
stat
```

### 10.2 `BlobStorePort`

Define operations for:

- conditional object creation;
- object metadata lookup;
- exact-generation streaming;
- V4 PUT grant generation;
- V4 GET grant generation;
- exact-generation deletion; and
- controlled prefix listing.

Only provider adapters import Google Cloud or future S3 libraries.

### 10.3 Audit boundary

The durable `audit_service` is not implemented. V0 will define a required,
narrow audit contract and a recording implementation for tests.

- There is no silent no-op audit implementation for staging or production.
- Storage bootstrap requires audit wiring explicitly.
- Tests assert exactly one safe audit call per material mutation or grant.
- Signed URLs, object keys, bucket names, media content, and checksums are not
  audit payload fields.
- Cloud Run deployment remains blocked until a durable audit adapter exists.

Atomic database-and-audit persistence remains an audit/outbox integration gate
and will not be falsely reported as complete.

## 11. Trusted key construction

Only UUIDs and controlled enum values may enter an object key.

The first supported path is:

```text
{environment}/organisations/{organisation_id}/matters/{matter_id}/
docs/{document_id}/v/{version_id}/original
```

The key builder rejects:

- absolute paths;
- `.` and `..` segments;
- slash or backslash characters inside identifiers;
- malformed UUIDs;
- original filenames;
- names, addresses, emails, matter labels, and document titles; and
- arbitrary caller-supplied path fragments.

Controlled derivative, export, voice, and corpus builders may be added for the
domain contract, but only document-original upload enters the first working
application flow.

## 12. Typed configuration

Extend the current `Settings` model with:

```env
DRAFTLY_DATABASE_URL=
DRAFTLY_DATABASE_MIGRATION_URL=

DRAFTLY_STORAGE_PROVIDER=gcs
DRAFTLY_STORAGE_ENVIRONMENT=staging
DRAFTLY_GCS_PROJECT_ID=draftly-502319
DRAFTLY_GCS_BUCKET=draftly-502319-staging-storage
DRAFTLY_GCS_LOCATION=asia-southeast1
DRAFTLY_GCS_SIGNING_SERVICE_ACCOUNT=draftly-storage-staging@draftly-502319.iam.gserviceaccount.com
DRAFTLY_STORAGE_UPLOAD_TTL_SECONDS=900
DRAFTLY_STORAGE_DOWNLOAD_TTL_SECONDS=300
DRAFTLY_STORAGE_MAX_UPLOAD_BYTES=52428800
DRAFTLY_STORAGE_REAL_DATA_APPROVED=false
```

Filesystem mode uses:

```env
DRAFTLY_STORAGE_PROVIDER=filesystem
DRAFTLY_STORAGE_ENVIRONMENT=local
DRAFTLY_FILESYSTEM_ROOT=<absolute-approved-local-path>
```

Rules:

- there is no provider default or silent provider fallback;
- an unconfigured storage module does not break Phase 0 liveness;
- selecting a provider requires its complete configuration;
- mixed filesystem and GCS settings are rejected;
- upload TTL is between 1 and 1800 seconds;
- download TTL is between 1 and 900 seconds;
- maximum upload size is positive;
- filesystem root is absolute;
- real-classified uploads are rejected while approval is false; and
- settings representations redact database URLs and any future secrets.

The safe `.env.example` activates filesystem mode for local development and
includes a commented staging GCS example. It contains no real secret, access
token, database password, signed URL, or JSON credential path.

## 13. Filesystem adapter

Implement the filesystem adapter before GCS.

- Resolve every key below the configured absolute root.
- Reject traversal, absolute keys, and symlink escape.
- Create objects exclusively and refuse overwrites.
- Stream writes while calculating SHA-256.
- Use the SHA-256 as the stable adapter generation because overwrites are
  forbidden.
- Store private sidecar metadata for content type, size, checksum, and
  generation.
- Require exact generation for stat, read, and delete operations.
- Exclude sidecars from object listings.
- Never produce a public or fake signed URL.

Local tests upload through `BlobStorePort` directly after reservation. The
browser-facing signed-upload path is GCS-only in V0.

## 14. GCS adapter

Use `google-cloud-storage` and Application Default Credentials.

- Normal ADC performs object operations.
- IAM Credentials impersonation targets the configured signing service
  account for V4 signing.
- No service-account JSON key is loaded or required.
- PUT grants bind `PUT`, the exact trusted key, declared content type, expiry,
  and `ifGenerationMatch=0`.
- GET grants bind `GET`, the exact trusted key, persisted generation, and
  expiry.
- Reads and deletes address the exact persisted generation.
- Generation is stored as text at the domain/database boundary.
- GCS CRC32C is recorded as supporting provider metadata but does not replace
  Draftly SHA-256.
- Provider timeouts, throttling, and unavailable errors are retryable and never
  converted to success.
- Not-found, forbidden, conflict, and precondition errors receive typed safe
  translations.

The storage readiness check validates the configured bucket's expected region,
uniform bucket-level access, public-access prevention, and versioning without
exposing their identifiers in the health response.

## 15. Upload reservation flow

`reserve_upload(ctx, scope, owner, constraints)` performs:

1. Organisation and matter scope validation.
2. Explicit `synthetic` or `real` data-classification validation.
3. Expected-size validation against the deployment maximum.
4. Declared media-type validation against the non-empty allowlist.
5. Optional expected SHA-256 validation.
6. Trusted document-original key construction.
7. Storage-object and reservation creation in one database transaction.
8. Signed PUT grant generation before commit so a signing failure leaves no
   persisted reservation.
9. Safe audit recording.
10. Return of reservation ID, storage object ID, method, expiry, and optional
    signed URL only.

The response never contains a bucket URI, permanent provider URL, object key,
credential, or provider response body.

## 16. Upload finalisation flow

`finalise_upload(ctx, reservation_id, claimed_sha256)` performs:

1. Organisation- and matter-scoped locking of reservation and object rows.
2. Scope equality validation between both rows and the request context.
3. Expired, rejected, reused, and already-finalised refusal.
4. Provider stat and exact generation capture.
5. Expected-size comparison.
6. Permitted media-type comparison.
7. Exact-generation streaming and backend SHA-256 calculation.
8. Comparison with both expected and claimed checksums when present.
9. Atomic object `available` and reservation `finalised` state changes.
10. Safe audit recording.

A size, media-type, or checksum mismatch marks the object
`integrity-failed`. An ambiguous provider state marks it `quarantined`. Neither
state is readable through normal storage operations.

The implementation never accepts the client's checksum without recalculating
it and never overwrites or silently replaces an object.

## 17. Download-grant flow

`issue_download_grant(ctx, storage_object_id, purpose, ttl)`:

- loads using organisation ID, matter ID, and storage object ID;
- hides tenant and matter mismatches as not found;
- requires `available` state;
- requires an exact persisted provider generation;
- defaults to 300 seconds and caps requests at 900 seconds;
- returns the URL only to the authorized caller;
- never persists or logs the URL; and
- audits only object ID, actor, purpose, and expiry.

`open_stream` and `stat` enforce the same scope and available-state rules.

## 18. Cloud Run preparation

There is no established Cloud Run deployment workflow, so V0 adds deployment
documentation rather than a new infrastructure system.

The documentation will cover:

- attaching
  `draftly-storage-staging@draftly-502319.iam.gserviceaccount.com`;
- providing non-secret storage environment variables;
- injecting database URLs through the future approved secret mechanism;
- keeping real-data approval false;
- using ADC rather than a JSON key;
- configuring health checks; and
- blocking deployment until durable audit wiring exists.

No Cloud Run resource is created or changed automatically.

## 19. CORS preparation

Add `infrastructure/gcs/cors.staging.example.json` containing only the approved
development origins, GET/PUT/HEAD methods, required response headers, and a
one-hour maximum age.

Document:

```bash
gcloud storage buckets update \
  gs://draftly-502319-staging-storage \
  --cors-file=infrastructure/gcs/cors.staging.example.json
```

Do not execute the command until the final Vercel staging origin is confirmed
and added. Wildcard origins are prohibited.

## 20. Testing strategy

### Unit tests

- Complete and incomplete provider configuration.
- TTL lower and upper bounds.
- Maximum upload size.
- Synthetic/real-data gate.
- Secret-safe settings representations.
- Trusted object keys and malformed identifiers.
- Domain state transitions.
- Typed error translation.
- Safe audit payloads.

### Repository and migration tests

- Alembic upgrade from empty database to head.
- Alembic downgrade from head to base.
- Schema constraints and required indexes.
- Object/reservation creation in one transaction.
- Organisation and matter filtering.
- Equal scope on linked rows.
- Row locking and optimistic concurrency.
- Duplicate key refusal.
- Reservation expiry and replay refusal.

### Blob-store contract tests

- Conditional creation.
- Duplicate-write refusal.
- Metadata stat.
- Exact-generation streaming.
- Exact-generation deletion.
- Controlled listing.
- Missing-object behavior.
- Provider-error translation.

Run this suite against filesystem first and structure it so the GCS sandbox can
reuse it later.

### Application tests

- Reservation creation.
- Size and media-type refusal.
- Expiry and replay refusal.
- Server-side checksum verification.
- Available, quarantined, and integrity-failed transitions.
- Download-grant scope and state enforcement.
- Cross-organisation and cross-matter existence hiding.
- Signed URL absence from logs, database rows, and audit records.

### GCS tests

- V4 PUT signing arguments and `ifGenerationMatch=0`.
- V4 GET signing against an exact generation.
- Exact-generation reads and deletes.
- ADC and impersonated-signing construction.
- Retryable and permanent exception mapping.
- Optional synthetic-only sandbox test against staging GCS.

GCS sandbox tests require an explicit opt-in variable and are not part of
normal CI.

## 21. CI and quality gates

Add a disposable PostgreSQL service to the backend CI job. CI never connects to
Neon or staging GCS.

Run:

```text
cd backend
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run alembic upgrade head
uv run alembic downgrade base
```

Run `npx markdownlint-cli2` against changed Markdown files. Existing unrelated
failures are reported separately.

## 22. Manual steps after implementation

The following remain manual:

1. Create or choose the Neon development/staging branch.
2. Store the pooled runtime URL as `DRAFTLY_DATABASE_URL`.
3. Store the direct URL as `DRAFTLY_DATABASE_MIGRATION_URL`.
4. Apply Alembic migrations using the direct URL.
5. Implement and wire the durable audit adapter.
6. Create the Cloud Run service.
7. Attach the existing storage service account to Cloud Run.
8. Configure non-secret storage variables.
9. Configure database URLs through the approved secret mechanism.
10. Add the final Vercel staging origin to the CORS example.
11. Apply CORS manually.
12. Deploy with `DRAFTLY_STORAGE_REAL_DATA_APPROVED=false`.
13. Run the opt-in synthetic GCS smoke test.

## 23. Acceptance criteria

The initial storage version is accepted when:

- all backend quality gates pass;
- migrations upgrade and downgrade a disposable PostgreSQL database;
- every storage repository query is organisation-scoped;
- matter-owned objects are matter-scoped;
- an original object cannot be overwritten;
- the GCS upload URL enforces conditional creation;
- finalisation calculates SHA-256 over the exact provider generation;
- only a verified object becomes available;
- download grants use the persisted generation;
- cross-tenant and cross-matter access reveals no existence signal;
- signed URLs occur only in returned grant values;
- no JSON service-account key or secret is introduced;
- real-classified uploads are refused; and
- existing Phase 0 health and error tests continue to pass.

## 24. Explicitly deferred work

V0 does not implement:

- a public storage HTTP API;
- document API routes;
- authentication or capability checks;
- MinIO;
- physical deletion commands;
- legal-hold integration;
- deletion receipts;
- orphan collection;
- automatic lifecycle deletion;
- derivative, export, voice, or corpus application flows;
- OCR or document processing;
- Cloud Run deployment automation;
- production data approval; or
- automatic CORS application.

These boundaries keep the first slice reviewable without weakening the storage
service's privacy, tenancy, evidence-integrity, or provider-neutrality rules.
