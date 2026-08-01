# Backend infrastructure and operations

Companion to `backend/backend-implementation-plan-v0.md`,
`jobs-and-workers.md`, and `services/README.md`. Records the platform choices
behind every service: datastores, object storage, queue, secrets, environments,
external providers, observability, and the backup and restore procedure.
Everything here sits behind a port (`plan §5.1`), so a swap is a configuration
change, not a code change.

## Principle: provider-neutral behind ports

The application talks to `DocumentRepository`, `ObjectStoragePort`, and
`JobQueuePort` — never to a specific vendor SDK. The database is plain
PostgreSQL reached through SQLAlchemy, Alembic, and `psycopg`. Object storage is
reached through an S3-compatible client. Because of that, moving from a managed
provider to a self-hosted server is a settings change and a data migration, with
no application rewrite. The exact production deployment stays an approval item
under plan §12.

## Database

### V0 — Neon (serverless PostgreSQL)

V0 uses **Neon** as the reference database for development, CI, and the initial
release.

- Standard PostgreSQL over the wire, so SQLAlchemy, Alembic, and `psycopg` are
  unchanged.
- **Branching** gives a throwaway database per pull request or per integration
  run, which is exactly the "disposable PostgreSQL instance" the Phase 1 and
  Phase 3 integration gates call for.
- Zero-ops and a free tier that covers V0.

Two Neon-specific settings the config must carry:

1. **Two connection strings.** The application uses the **pooled** endpoint
   (PgBouncer). **Alembic migrations use the direct, unpooled endpoint** —
   migrations misbehave through a transaction pooler.
2. `sslmode=require` in the URL. Autosuspend adds a sub-second cold start on the
   free tier, which is harmless for development.

Confidential-data boundary: Neon is managed cloud infrastructure. Real client
matter data (party names, deed and registry numbers, verified particulars) may
only land on it once data residency, a processor agreement, and lawyer sign-off
are confirmed (PDPA 2022). Until then V0 runs on synthetic and pilot data per
plan §10.

### V1 (production) — self-hosted PostgreSQL on local servers

For the V1 production release the database moves to **PostgreSQL on the team's
own local or on-premises servers**. This keeps confidential client data inside
infrastructure the practice controls, which fits the privacy posture for real
conveyancing bundles. The migration is a `pg_dump` and restore plus a connection
string change; no application code changes because the access layer is already
provider-neutral.

## Object storage

Files never live in the database. The database holds only metadata and a
`storage_key`; the bytes live in an S3-compatible object store behind
`ObjectStoragePort`.

- **V0 development and demo:** MinIO (S3-compatible, runs in a container) or a
  local filesystem adapter. No cloud, no client data.
- **V1 production:** self-hosted MinIO on the same local or on-premises servers
  as the database, for the same confidentiality reason. Still S3-compatible, so
  the adapter does not change.

Key layout, one bucket with separate prefixes and separate retention (plan §10):

```text
matters/{matter_id}/
  docs/{doc_id}/v/{version_id}/original      # immutable, write-once, long retention
  docs/{doc_id}/v/{version_id}/derivatives/  # OCR text, layout, quality, preview — rebuildable
  exports/{export_id}/...                     # approved DOCX/PDF plus manifest
```

Originals are written once and never overwritten; derivatives are rebuildable
and non-authoritative; exports are lawyer-controlled outputs. Bytes reach the
browser only through a short-lived signed URL, never a raw path.

### Storage lifecycle rules

- **Originals**: write-once, versioned, never overwritten, never deleted by any
  sweep. Deletion happens only through an approved disposition
  (`retention-service.md` §5).
- **Derivatives**: rebuildable. A bucket lifecycle rule may expire derivatives
  older than 90 days for closed matters; the rebuild job restores them on
  demand.
- **Exports**: retained per policy; the **signed URL** expires in minutes, the
  **object** does not. Expiring a URL is not destruction.
- **Nothing under an active legal hold is collected, expired, or deleted**,
  including by the orphan-blob sweep (`jobs-and-workers.md` §7).
- Every key is organisation-prefixed in V1 so a tenant's data can be exported or
  isolated without a scan.

## Queue and workers

V0 uses a **PostgreSQL-backed outbox with `SELECT … FOR UPDATE SKIP LOCKED`**
as both the event bus and the job queue, behind `JobQueuePort` and `EventPort`.
That avoids a second infrastructure dependency for a workload measured in
thousands of jobs per day, and it makes "enqueue in the same transaction as the
state change" trivially true rather than a two-phase problem.

The full protocol — claim, lease, retry, backoff, dead-letter, scheduled jobs —
is in `jobs-and-workers.md`. Swapping to a broker later is an adapter change;
the outbox table stays either way, because it is what makes the publish
transactional.

Plan §12 lists queue technology as an approval item. This is the recommended
default, not a closed decision.

## Environments

| Environment | Database | Object store | Providers | Data |
| --- | --- | --- | --- | --- |
| Local | Neon branch or containerised PostgreSQL | MinIO container | Console and fake adapters only | Synthetic |
| CI | Neon branch per pull request, dropped after | MinIO service container | Fake adapters; recorded provider fixtures | Synthetic |
| Preview | Neon branch per deployment | MinIO | Sandbox provider keys, allowlisted recipients | Synthetic |
| Staging | Neon | MinIO | Real providers, restricted recipient allowlist | Synthetic and approved pilot |
| Production V1 | Self-hosted PostgreSQL | Self-hosted MinIO | Real providers | Real, after the §12 gates |

Neon branching gives the disposable database the Phase 1 and Phase 3 integration
gates require. A CI branch is created from a schema-only baseline, migrated, and
dropped — never branched from a database holding pilot data.

**No production credential, address, or dataset appears in local, CI, preview, or
demo environments.** Non-production email sends only to an explicit synthetic
allowlist (`notification-service.md` §11).

## Configuration and secrets

- Settings are a typed `pydantic-settings` model validated at startup. A missing
  or malformed required setting fails the boot; it does not default silently.
- Secrets come from the environment or an approved secret manager. Never from a
  committed `.env`, never from a database row, never echoed by a health route or
  an error body.
- Required secret groups: database URLs (pooled and direct), object-store
  credentials, Clerk keys, Google Cloud service account, Gemini API key, Resend
  API key and webhook secret, PayHere merchant credentials and webhook secret,
  the party-identifier encryption key, and the outbox signing key.
- **The party identity key is separate and rotatable** (`party-service.md` §12).
  It is not the general database key, and rotation re-wraps rather than
  re-encrypts in place.
- Least privilege per credential, and per-environment keys. The Resend key lives
  only in the notification worker's environment.
- A `provider_data_approval` flag gates any real-data call to Document AI or
  Gemini; while false the adapter refuses non-synthetic documents and routes
  them to manual review (`document-processing.md` §10A).

## External providers

| Provider | Used for | Port | Gate before real data |
| --- | --- | --- | --- |
| Clerk | Identity, sessions, authentication email | `IdentityPort` | Environment and role mapping approved (plan §12) |
| Google Document AI | Primary OCR and quality | `OcrPort` | Region, retention, deletion, training-use, quota, cost, exit — recorded and approved |
| Gemini | Classification, OCR fallback, extraction, voice | `ClassifierPort`, `OcrPort`, `ExtractorPort`, `LiveTranscriptionPort` | Same gate as Document AI |
| Resend | Application email | `EmailPort` | Domain verified with SPF, DKIM, DMARC; processor terms reviewed |
| PayHere | Recurring payments | `BillingProviderPort` | Onboarding, settlement, prices, refunds, retention |
| Screening provider | Sanctions and PEP | `ScreeningPort` | May be a manual-entry adapter in V0 |

Every one is behind a port, and every one has a fake used by CI. No test sends a
real email, charges a real card, or ships a real document to a provider.

## The retrieval-engine boundary

`research_service` reads the legal corpus through `LegalRetrievalPort`, backed
by the existing Python engine in the research repository. Plan §12 lists the
exact package boundary as an open approval item and it is still open. Until it
closes, the rule from plan §6 holds: production reaches the engine only through
a **versioned package or interface**, never by importing arbitrary research
paths, and never by walking research-repository directories at runtime. The
index is built from a signed corpus release manifest
(`corpus-governance-service.md` §7).

## The email-template build

`backend/email-templates/` is a separate pnpm project (React Email) that does
**not** run inside the FastAPI process (`notification-service.md` §3). Its
pipeline: render and snapshot in CI, review, then one-way publish of approved
versions to Resend templates, recording the deployment. Draft templates never
publish. Rollback selects an earlier published deployment and never edits
history.

## Observability

- **Structured logs** with `correlationId`, `causationId`, `organisationId`, and
  job or request identifiers. Never payload bodies, transcript fragments,
  extracted values, identifiers, recipient addresses, or secrets
  (`service-definition-of-done.md` §4.7).
- **Metrics**: request rate and latency per route class; job queue depth, oldest
  pending age, dead-letter count, lease reaps; provider latency and error class;
  usage against plan quotas.
- **Traces** across API → application → port → adapter, with provider spans.
- **Alerts**: any dead-letter arrival, oldest-pending age over budget, lease
  reaping above baseline, provider error rate, quota approaching exhaustion,
  audit chain-verification failure, and `provider_data_approval` being enabled.

## Backup, restore, and recovery

Plan §10 requires this before lawyer testing, and it was not written down.

- **Database**: Neon point-in-time restore in V0; in V1, nightly `pg_dump` plus
  continuous WAL archiving to separate storage. Retain 30 daily, 12 monthly.
- **Object store**: versioned buckets with cross-device replication in V1.
  Originals and exports are backed up; derivatives are not, because they rebuild.
- **Restore drill**: quarterly, into an isolated environment, timed. A restore
  that has never been executed is not a backup.
- **Recovery targets**: RPO 15 minutes, RTO 4 hours for V1. Confirm with the
  practice before production.
- **Post-restore reconciliation is mandatory.** A restore can reinstate records
  that were lawfully destroyed. Before the environment returns to service, run
  the tombstone reconciliation sweep (`retention-service.md` §8) and the audit
  chain verification, and record both results.
- **Consistency**: database and object store are backed up independently, so a
  restore may leave orphan blobs or dangling keys. The orphan sweep and a
  key-existence check run as part of the restore runbook, not opportunistically.

## Data protection posture

- Real client matter data may reach managed cloud infrastructure only once data
  residency, a processor agreement, and lawyer sign-off are confirmed under
  PDPA 2022. This applies to Neon, Document AI, Gemini, Resend, and PayHere
  alike, and hardest to the OCR path, where the payload is the deed itself.
- Until then V0 runs on synthetic and pilot data (plan §10).
- Personal data inventory, retention schedule, and erasure handling are owned by
  `retention_service`; the periods themselves are a legal-review item.
- `data/raw/` in the research repository never reaches this backend, its
  fixtures, its logs, or its screenshots.

## Summary

| Concern | V0 | V1 production |
| --- | --- | --- |
| Database | Neon serverless PostgreSQL (synthetic and pilot data) | Self-hosted PostgreSQL on local servers |
| Object storage | MinIO or filesystem adapter | Self-hosted MinIO on local servers |
| Queue | PostgreSQL outbox with `SKIP LOCKED` | Same, or a broker behind `JobQueuePort` |
| Workers | One runner process plus a leader-elected scheduler | Same, scaled horizontally |
| Access layer | SQLAlchemy, Alembic, S3-compatible client | Identical — no code change |
| Secrets | Environment or secret manager, per-environment keys | Same, plus rotation schedule |
| Backups | Neon PITR | `pg_dump` + WAL archive, versioned buckets, quarterly drill |
| Deployment sign-off | Synthetic and pilot data only | Plan §12: gated on residency, processor agreement, lawyer approval |
