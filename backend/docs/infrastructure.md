# Backend infrastructure — databases and storage

Companion to `backend/backend-implementation-plan-v0.md`. Records the datastore
and object-storage choices for each release. Everything here sits behind a port
(`§5.1`), so a swap is a configuration change, not a code change.

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

## Summary

| Concern | V0 | V1 production |
| --- | --- | --- |
| Database | Neon serverless PostgreSQL (synthetic and pilot data) | Self-hosted PostgreSQL on local servers |
| Object storage | MinIO or filesystem adapter | Self-hosted MinIO on local servers |
| Access layer | SQLAlchemy, Alembic, S3-compatible client | Identical — no code change |
| Deployment sign-off | Synthetic and pilot data only | Plan §12: gated on residency, processor agreement, lawyer approval |
