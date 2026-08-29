# storage_service — implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`backend/docs/infrastructure.md`, `document-service.md`,
`retention-service.md`, and `jobs-and-workers.md`.

This service is Draftly's provider-neutral storage control plane. Neon stores
object metadata and workflow state; Google Cloud Storage (GCS), MinIO, or the
local filesystem stores bytes. No application service imports a Google or S3
SDK directly.

## 0. Implementation status

**This service does not exist as a module.** There is no `src/modules/storage/`,
no `ObjectStoragePort`, and no `BlobStorePort`. What ships today is the narrow
slice the RTA evidence path needs, built against the existing
`SourceFileStoragePort` in the document module:

| Designed here | Shipped today |
| --- | --- |
| `ObjectStoragePort` → `BlobStorePort` → `GcsBlobStore` | `SourceFileStoragePort` → `GcsSourceFileStorage` |
| `put_immutable` conditional on absence | `put()` with `if_generation_match=0` |
| Reads resolve the exact pinned generation | `get(key, version=...)` pins the generation |
| Verify checksums at finalisation | `processing_job` verifies SHA-256 after every download |
| `quarantined` / `integrity-failed` object states | a typed `SourceObjectIntegrityError`; the read fails and the bytes go nowhere |
| Upload reservations, signed URL grants | not built — uploads go through the API |
| Deletion receipts, tombstones, orphan sweeps | not built |
| MinIO / S3 adapter | not built, and no S3 code exists |

`validate_object_key` and `content_sha256` in
`modules/document/infrastructure/object_store_support.py` are the designated
lift-out seam: they are provider-neutral and move into `storage_service`
unchanged. Provider-error translation is isolated as `_translate` in
`storage_gcs.py` for the same reason.

Deliberate deviations, so the gap is visible rather than silent:

- Object metadata lives on the `source_files` table, not a `storage_objects`
  table. There is no `providerGeneration` column — the generation *is*
  `storage_object_version`.
- Verification happens on read rather than at finalisation, because there is no
  finalisation step to hang it on.
- An integrity failure raises rather than transitioning the object to
  `integrity-failed`. Quarantining needs an object state machine this slice does
  not have. **Follow-up:** add `ProcessingFailureReason.INTEGRITY_FAILED`, an
  explanation key, and the frontend label, so a lawyer sees a reason rather than
  a 500.
- The bucket-policy checks in §7 run once per process in `bootstrap._gcs_client`,
  not in a storage service.

## 1. What it owns

`storage_service` owns:

- provider-neutral object references and storage metadata;
- upload reservations and finalisation;
- immutable writes, exact-generation reads, and short-lived signed URLs;
- checksum, size, media-type, and provider-generation verification;
- storage inventory and orphan reconciliation;
- physical deletion after the record-owning service supplies a valid,
  hold-cleared destruction command; and
- startup validation of the selected storage adapter and its non-secret
  configuration.

It does **not** own:

- documents, versions, derivatives, exports, voice captures, or corpus records;
- the decision to retain or destroy a record;
- legal holds, retention schedules, or tombstones;
- user or matter authorization;
- database schemas belonging to another service;
- a user's Google Cloud credentials; or
- provider secrets in Neon.

The service owns the bytes and their physical location, not the legal record.
For example, `document_service` owns a `DocumentVersion` and delegates its blob
operations to `storage_service`. `retention_service` decides whether destruction
is allowed; the record-owning service requests the physical delete.

## 2. Where it sits

```text
document / export / voice / corpus application service
                         |
                         v
                 ObjectStoragePort
                         |
                         v
              application/storage_service.py
                  |                 |
                  v                 v
       StorageObjectRepository   BlobStorePort
                  |                 |
                  v                 +-- GcsBlobStore
        Neon/PostgreSQL             +-- S3BlobStore (MinIO)
                                    +-- FilesystemBlobStore
```

There is no public storage API. A browser receives an upload or download grant
only through the owning service after that service re-checks `user_id`,
matter, capability, and record access. Health endpoints may expose only
`ready | degraded | unavailable`, never bucket names, object keys, account
identifiers, signed URLs, credentials, or connection strings.

The dependency direction remains:

```text
API -> owning application service -> ObjectStoragePort -> storage_service
    -> StorageObjectRepository + BlobStorePort -> provider adapters
```

## 3. Domain models

### StorageObject

```text
StorageObject
  id
  userId
  matterId?             # required for matter evidence and matter exports
  ownerService
  ownerType
  ownerId
  objectClass           # original | derivative | export | voice | corpus
  provider              # filesystem | minio | gcs
  bucketRef             # logical bucket alias, not a credential
  objectKey
  providerGeneration?   # required for GCS finalised objects
  sha256
  providerChecksum?     # CRC32C for GCS when available
  sizeBytes
  mediaType
  state                 # reserved | available | quarantined |
                        # pending-deletion | deleted | integrity-failed
  createdAt
  finalisedAt?
  deletedAt?
```

`(provider, bucketRef, objectKey, providerGeneration)` is unique. All rows carry
`userId`; matter-scoped rows also carry `matterId`. An object reference
returned to another service uses the Draftly `StorageObject.id`, never a raw
provider URL.

### UploadReservation

```text
UploadReservation
  id
  userId
  matterId?
  ownerService
  ownerType
  ownerId
  objectClass
  objectKey
  expectedSizeBytes
  allowedMediaTypes
  expectedSha256?
  state                 # active | finalised | expired | rejected
  expiresAt
  createdBy
```

A reservation constrains one exact key, HTTP method, expiry, maximum size, and
media type. It cannot be reused for another user, matter, or owner.

### DeletionCommand and DeletionReceipt

```text
DeletionCommand
  commandId
  userId
  recordScope
  storageObjectIds
  policyId
  policyVersion
  approvedBy
  approvedAt
  holdCheckedAt

DeletionReceipt
  commandId
  deletedObjectIds
  alreadyAbsentObjectIds
  failedObjectIds
  completedAt
```

The command is supplied by the record-owning service after
`retention_service` approval. The storage service re-checks the hold through
`HoldStatusPort` immediately before every destructive provider operation.

## 4. Ports

### Port exposed to application services

`ObjectStoragePort` exposes provider-neutral operations:

```text
reserve_upload(scope, owner, constraints) -> UploadGrant
finalise_upload(reservation_id, claimed_sha256) -> StoredObjectRef
put_immutable(scope, owner, stream, metadata) -> StoredObjectRef
put_derivative(scope, owner, stream, metadata) -> StoredObjectRef
open_stream(storage_object_id) -> ByteStream
issue_download_grant(storage_object_id, purpose, ttl) -> DownloadGrant
stat(storage_object_id) -> StoredObjectMetadata
delete_authorised(command) -> DeletionReceipt
```

The owning service performs domain authorization before calling the port. The
storage service independently checks that the requested object scope matches
the authenticated `RequestContext`; defence in depth does not replace the
owner's check.

### Ports used by storage_service

- `StorageObjectRepository` — storage objects and upload reservations in
  PostgreSQL, always scoped by `user_id`.
- `BlobStorePort` — conditional put, stat, stream, sign, list, and
  generation-matched delete.
- `HoldStatusPort` — authoritative hold check for a record scope. Failure is
  fail-closed.
- `AuditPort` — records reservations, finalisation, grants, integrity failures,
  reconciliation, and deletion without logging content or URLs.
- `ClockPort` and `IdGeneratorPort` — deterministic tests.

`BlobStorePort` is implemented by `GcsBlobStore`, `S3BlobStore`, and
`FilesystemBlobStore`. Provider exceptions are translated to typed storage
errors at this boundary.

## 5. Core methods

### reserve_upload(ctx, scope, owner, constraints) -> UploadGrant

1. Confirm the supplied scope belongs to `ctx.actorId` and, when
   matter-scoped, `ctx.matterId`.
2. Validate size and media-type constraints before contacting a provider.
3. Build the key from trusted IDs; never accept a client-provided path.
4. Insert an expiring reservation in Neon.
5. Return either a short-lived, exact-key signed upload grant or an API upload
   token, according to the selected adapter.
6. Audit the grant without recording its URL or signature.

### finalise_upload(ctx, reservation_id, claimed_sha256) -> StoredObjectRef

1. Lock the active reservation and reject expired or reused reservations.
2. Read provider metadata for the exact key and generation.
3. Verify size, media type, provider checksum, and the application SHA-256. A
   client claim is never accepted without server-side verification. For a
   direct GCS upload, stream the pinned generation through the verifier when no
   trusted provider SHA-256 exists; GCS CRC32C alone does not replace Draftly's
   evidence SHA-256.
4. For GCS, pin the live object's generation. For MinIO/filesystem, pin the
   adapter's immutable version identifier where available.
5. Mark the storage object `available` and the reservation `finalised` in one
   PostgreSQL transaction.
6. Return the Draftly object reference; never return a permanent provider URL.

If verification fails, mark the object `quarantined` or
`integrity-failed`, deny reads, and enqueue controlled cleanup. Do not silently
replace it.

### put_immutable(ctx, scope, owner, stream, metadata) -> StoredObjectRef

Stream the upload while computing SHA-256. The provider operation must be
conditional on absence. GCS uses `if_generation_match=0`; an existing live
object returns a conflict rather than being overwritten. Persist the returned
generation and checksums. A retry with the same idempotency key returns the
same object only after its metadata matches.

### issue_download_grant(ctx, object_id, purpose, ttl) -> DownloadGrant

Re-check scope and owner authorization, require `state=available`, cap `ttl` at
the configured maximum, bind the grant to `GET` and the exact object generation,
and audit the purpose. Signed URLs are bearer credentials: never log, persist,
cache, email, or include them in events.

### delete_authorised(command) -> DeletionReceipt

1. Lock the target storage rows and validate the command scope.
2. Ask `HoldStatusPort` again. A timeout, error, or active hold refuses deletion.
3. Mark rows `pending-deletion`.
4. Delete the exact provider generation, not merely the current object name.
5. Mark confirmed objects `deleted`, preserving non-content metadata and the
   deletion receipt. Report partial failure explicitly.
6. The record-owning service returns the receipt to `retention_service`; only
   then may retention mark the disposition destroyed.

The method is idempotent on `commandId`. `alreadyAbsent` is not treated as proof
of prior authorized destruction; it triggers reconciliation and audit review.

### collect_orphans(as_of) — scheduled daily

The `storage.collect-orphans` job handles both halves of database/blob drift:

- expired reservations whose provider object exists but has no finalised row;
- finalised rows whose exact provider generation is absent; and
- provider objects under a Draftly-managed prefix that have no storage row and
  are older than 24 hours.

An orphan is deleted only when its trusted key can be mapped to a user
and record scope, the grace period has elapsed, and `HoldStatusPort` confirms no
hold. Unknown or malformed keys are quarantined for an operator; they are never
deleted automatically.

## 6. Key layout

The application constructs keys; callers cannot supply them.

```text
{environment}/users/{user_id}/matters/{matter_id}/
  docs/{doc_id}/v/{version_id}/original
  docs/{doc_id}/v/{version_id}/derivatives/{derivative_kind}/{artifact_id}
  exports/{export_id}/{artifact_id}
  voice/{capture_id}/{artifact_id}

{environment}/users/{user_id}/corpus/
  sources/{source_id}/v/{version_id}/{artifact_id}
```

IDs are opaque server-generated identifiers. File names, party names, matter
references, email addresses, and document titles never appear in a key. The
logical layout is identical across GCS, MinIO, and filesystem adapters.

## 7. Configuration contract

All settings are typed, validated at startup, and sourced from environment
variables or an approved secret manager. Values shown below are names and safe
defaults, not credentials.

### Shared PostgreSQL/Neon settings

| Setting | Required | Rule |
| --- | --- | --- |
| `DRAFTLY_DATABASE_URL` | yes | Runtime pooled Neon URL; `sslmode=require` and `channel_binding=require` outside local containers |
| `DRAFTLY_DATABASE_MIGRATION_URL` | migration process | Direct, unpooled Neon URL; never exposed to the web process unless that process runs migrations |
| `DRAFTLY_DATABASE_POOL_SIZE` | no | Small bounded application pool; default `5` |
| `DRAFTLY_DATABASE_MAX_OVERFLOW` | no | Default `5`; do not multiply unbounded pools across workers |
| `DRAFTLY_DATABASE_POOL_TIMEOUT_SECONDS` | no | Default `30` |

The storage service uses the same database/session factory as every application
service. It does not create a separate Neon project or manage Neon branches.
Application traffic uses the pooled endpoint; Alembic and administrative tools
use the direct endpoint.

### Shared storage settings

| Setting | Required | Rule |
| --- | --- | --- |
| `DRAFTLY_STORAGE_PROVIDER` | yes | `filesystem`, `minio`, or `gcs`; no silent fallback |
| `DRAFTLY_STORAGE_ENVIRONMENT` | yes | Fixed key prefix such as `local`, `ci`, `preview`, or `staging` |
| `DRAFTLY_STORAGE_DOWNLOAD_TTL_SECONDS` | no | Default `300`, maximum `900` |
| `DRAFTLY_STORAGE_UPLOAD_TTL_SECONDS` | no | Default `900`, maximum `1800` |
| `DRAFTLY_STORAGE_MAX_UPLOAD_BYTES` | yes | Positive deployment limit; owning services may impose a lower limit |
| `DRAFTLY_STORAGE_REAL_DATA_APPROVED` | yes | Default `false`; GCS adapter rejects non-synthetic data while false |

### GCS adapter settings

| Setting | Required for `gcs` | Rule |
| --- | --- | --- |
| `DRAFTLY_GCS_PROJECT_ID` | yes | Expected Google Cloud project ID |
| `DRAFTLY_GCS_BUCKET` | yes | Private, environment-specific bucket |
| `DRAFTLY_GCS_LOCATION` | yes | Must equal the approved residency location |
| `DRAFTLY_GCS_KMS_KEY_NAME` | when CMEK is approved as required | Full CryptoKey resource name; never key material |
| `DRAFTLY_GCS_SIGNING_SERVICE_ACCOUNT` | for signed URLs | Service-account email allowed to sign; not a JSON key |

Use Application Default Credentials. In deployed environments prefer an
attached workload identity or Workload Identity Federation. A service-account
JSON key is not committed, stored in Neon, or placed in a general-purpose
`.env`. `GOOGLE_APPLICATION_CREDENTIALS` is allowed only for controlled local
development when federation is unavailable, and the referenced file remains
outside the repository.

### MinIO and filesystem settings

| Setting | Required | Rule |
| --- | --- | --- |
| `DRAFTLY_MINIO_ENDPOINT` | for `minio` | HTTPS outside a local container network |
| `DRAFTLY_MINIO_BUCKET` | for `minio` | Environment-specific private bucket |
| `DRAFTLY_MINIO_ACCESS_KEY` | for `minio` | Secret |
| `DRAFTLY_MINIO_SECRET_KEY` | for `minio` | Secret |
| `DRAFTLY_FILESYSTEM_ROOT` | for `filesystem` | Absolute path inside an explicitly approved local data directory |

Startup refuses mixed-provider settings, a missing bucket, an unapproved GCS
location, public bucket access, disabled uniform access, a writable filesystem
root outside the configured data directory, or a real-data environment with
`DRAFTLY_STORAGE_REAL_DATA_APPROVED=false`.

## 8. GCS bucket and IAM baseline

Each environment has its own bucket and service identity. The bucket must have:

- public access prevention enforced;
- uniform bucket-level access enabled; object ACLs are never used;
- default Google-managed encryption, or the approved CMEK when required;
- CORS restricted to exact Draftly frontend origins, only required methods and
  headers, and no wildcard origin with credentials;
- Cloud Audit Logs Data Access logging enabled for production/pilot approval;
- object versioning configured as recovery defence, not as permission to
  overwrite originals; and
- lifecycle rules that cannot delete record-scoped objects independently of the
  application retention workflow.

IAM is granted at the bucket, not project-wide:

| Identity | Minimum responsibility |
| --- | --- |
| API runtime | Create constrained signed grants and read metadata; no bucket administration |
| storage worker | Create/read objects and delete exact generations after an authorized command |
| migration/deployment | Validate bucket policy; no routine object-data access |
| human operator | No default object access; time-bound audited elevation for incidents |

Do not grant Editor, Owner, or Storage Admin to the runtime identity. If a
predefined role is broader than the required operations, define and review a
custom role.

## 9. Environment matrix

| Environment | Metadata | Bytes | Data allowed |
| --- | --- | --- | --- |
| Local | Neon dev branch or container PostgreSQL | filesystem or MinIO | synthetic only |
| CI | disposable Neon branch | MinIO service container or filesystem temp root | generated fixtures only |
| Preview | Neon branch per deployment | GCS preview bucket | synthetic only |
| Staging | Neon staging branch | GCS staging bucket | synthetic; approved pilot only after provider gate |
| Production V1 | approved PostgreSQL deployment | approved GCS or self-hosted MinIO deployment | real data only after all infrastructure and legal gates |

Selecting GCS is a deployment setting, not blanket approval for real client
material. Before real matter data reaches Neon or GCS, record the location,
processor terms, subprocessors, retention/deletion behaviour, incident process,
encryption decision, access model, export path, cost, and lawyer approval.

## 10. Transactions and failure handling

PostgreSQL and an object store do not share a transaction. The implementation
uses explicit states and reconciliation:

| Failure | Required result |
| --- | --- |
| Reservation commit fails | No usable grant returned |
| Upload succeeds, finalisation fails | Expiring reservation; orphan sweep after grace period |
| Finalisation commits, owner transaction fails | Available unclaimed object; reconciliation flags it, never immediate deletion |
| Provider stat/checksum fails | Quarantine and retry; never mark available |
| Signed URL creation fails | No persisted partial state; safe retry |
| Delete succeeds, receipt commit fails | Retry exact generation; reconcile provider absence; audit ambiguity |
| Neon unavailable | Fail closed for grants, writes, and deletes; existing signed URLs expire naturally |
| GCS unavailable | Metadata reads may continue; byte reads/writes return a typed retryable error |

No operation converts a provider timeout into success. Retry policy is bounded,
jittered, and idempotent.

## 11. Invariants

| Invariant | How |
| --- | --- |
| Provider-neutral application code | Only `BlobStorePort` adapters import provider SDKs |
| Original bytes never overwritten | Trusted unique key plus conditional create; GCS `if_generation_match=0` |
| Reads resolve the exact object | Draftly ID resolves to bucket, key, and pinned provider generation |
| Every object is tenant-scoped | `userId` on every row and user prefix on every key |
| Matter evidence cannot cross matters | Scope check in owner and storage facade; non-member existence hidden |
| Signed URLs are short-lived bearer credentials | Exact method/key/generation, capped TTL, never logged or stored |
| Client metadata is untrusted | Server verifies checksum, size, media type, and provider metadata |
| Legal holds win | Destructive paths synchronously re-check `HoldStatusPort` and fail closed |
| Provider lifecycle cannot bypass retention | No autonomous lifecycle deletion for originals or exports |
| Provider secrets never enter Neon or Git | ADC/secret manager only; settings redact secrets |
| Unknown objects are not guessed away | Malformed/unmapped inventory is quarantined for review |
| Deletion is provable and idempotent | Command ID, exact generation, receipt, tombstone flow, and audit |

## 12. Tests

- **Unit:** key construction, scope validation, configuration matrix, TTL caps,
  reservation state transitions, checksum comparison, idempotent deletion, and
  provider-error translation.
- **Contract:** run the same `BlobStorePort` suite against filesystem, MinIO,
  and the GCS emulator/fake; conditional create, exact-generation read/delete,
  signing, stat, list, and retry semantics must match.
- **Integration:** real PostgreSQL plus storage emulator for reservation through
  finalisation; database/provider partial failures; orphan reconciliation;
  missing generation; and deletion receipt recovery.
- **GCS sandbox:** private bucket policy validation, public-access prevention,
  uniform access, least-privilege identity, signed upload/download expiry,
  checksum verification, and `if_generation_match=0` overwrite refusal. Use
  generated fixtures only.
- **Security:** cross-user and cross-matter access returns 404; key
  traversal rejected; forged/replayed reservation rejected; signed URL absent
  from logs/events; held object cannot be deleted; runtime cannot administer
  the bucket.
- **Recovery:** inventory rebuild, missing-object detection, exact-generation
  restore verification, and a quarterly database/object-store restore drill.

## 13. Implementation order

1. Add typed settings and startup validation with `filesystem` as the local
   adapter.
2. Add `StorageObject` and `UploadReservation` migrations and repositories.
3. Define `BlobStorePort` and its shared contract suite.
4. Implement filesystem and MinIO adapters for local/CI.
5. Implement `GcsBlobStore` using ADC, conditional operations, checksums, and
   exact-generation references.
6. Route `document_service` through the storage facade without changing its
   document API contract.
7. Move `storage.collect-orphans` ownership to `storage_service` and add the
   hold-aware inventory sweep.
8. Integrate export, voice, and corpus storage one owner at a time.
9. Complete the GCS sandbox and recovery gates before enabling the adapter in
   staging.

## 14. Decisions and approval gates

Selected defaults:

1. **Neon holds metadata only; object bytes never enter PostgreSQL.**
2. **GCS is the managed cloud adapter; filesystem and MinIO remain local/CI and
   self-hosted options.**
3. **Application services depend on `ObjectStoragePort`; provider mechanics
   live behind `BlobStorePort`.**
4. **No public storage endpoints and no permanent object URLs.**
5. **Real-data use remains blocked until the existing residency, processor,
   security, deletion, and lawyer-approval gates are recorded.**

Still requiring explicit approval before real client data:

- exact Neon and GCS regions;
- Google Cloud processor and subprocessor review;
- GCS retention policy, version-recovery window, and CMEK decision;
- whether Production V1 uses approved GCS or self-hosted MinIO; and
- backup destination and cross-region/cross-provider recovery policy.

## References

- [Neon connection pooling](https://neon.com/docs/connect/connection-pooling)
- [GCS request preconditions](https://cloud.google.com/storage/docs/request-preconditions)
- [GCS signed URLs](https://cloud.google.com/storage/docs/access-control/signed-urls)
- [GCS uniform bucket-level access](https://cloud.google.com/storage/docs/uniform-bucket-level-access)
- [GCS public access prevention](https://cloud.google.com/storage/docs/public-access-prevention)
