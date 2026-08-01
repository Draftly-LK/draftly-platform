# Jobs, outbox, and workers

Companion to `events.md`, `infrastructure.md`, and the six service docs that
each previously re-specified this pattern slightly differently:
`document-service.md` §6, `export-service.md` §6, `obligations-service.md`
§13.6, `notification-service.md` §6.3, `billing-service.md` §7.3, and
`task-service.md` §9.

It also fills a gap none of them covered: **nothing said what runs the scheduled
work.** The reminder sweep, the outbox drain, the orphan-blob collector, the
lease reaper, and the corpus rebuild all had a described behaviour and no
runtime.

## 1. Runtime topology for V0

One FastAPI deployable and one worker process, both from the same image and the
same settings module.

```text
api        uvicorn draftly_api.main:app        HTTP only, never blocks on a job
worker     draftly_api.workers.runner          claims and executes queued jobs
scheduler  draftly_api.workers.runner --sched  one leader, fires timed jobs
```

The scheduler is a mode of the same runner, not a third image. It elects a
leader through a Postgres advisory lock so running two replicas is safe; the
loser idles. A separate notification or research deployment is justified only
after measured load says so (`notification-service.md` §3).

## 2. The transactional outbox

Every domain event and every job enqueue is written to `outbox` **in the same
transaction as the state change**. Nothing calls a queue inside a transaction,
and nothing enqueues before commit.

```sql
outbox (
  id              bigserial primary key,
  organisation_id uuid        not null,
  kind            text        not null,   -- 'event' | 'job'
  name            text        not null,   -- registry event name, or job type
  payload         jsonb       not null,   -- envelope + data, or job message
  idempotency_key text        not null,
  available_at    timestamptz not null default now(),
  claimed_at      timestamptz,
  claimed_by      text,
  attempts        int         not null default 0,
  state           text        not null default 'pending',
  last_error      text,
  created_at      timestamptz not null default now(),
  unique (kind, name, idempotency_key)
)
```

The uniqueness constraint is the permanent duplicate guard. A provider-side
idempotency key (Resend, PayHere) is an additional short-lived protection, not a
replacement (`notification-service.md` §9).

A sweeper drains `pending` rows to the queue adapter after commit. If the
adapter is the Postgres queue itself (the V0 default), draining is a state
transition on the same row and the two-phase risk disappears.

## 3. Claim protocol

Every worker claims the same way. This is the one implementation; services do
not write their own.

```sql
update outbox
   set state = 'claimed', claimed_at = now(), claimed_by = :worker_id,
       attempts = attempts + 1
 where id in (
   select id from outbox
    where state = 'pending' and available_at <= now()
    order by available_at
    for update skip locked
    limit :batch
 )
returning *;
```

- `SKIP LOCKED` gives contention-free parallel claiming.
- **Claiming must be safe to run twice.** The handler is idempotent on
  `idempotency_key`; a redelivery produces one effect.
- A claim holds a **lease** of `lease_seconds` (default 300, overridable per job
  type). The lease reaper returns rows whose `claimed_at + lease` has passed to
  `pending`. A crashed worker therefore costs one lease interval, not a lost job.
- A long job renews its lease by heartbeat rather than taking a long default.

## 4. Retry, backoff, dead-letter

| Outcome | Handling |
| --- | --- |
| Success | `state = 'done'`, result persisted in the owning table |
| Retryable failure (timeout, 5xx, rate limit, transient lock) | `state = 'pending'`, `available_at = now() + backoff(attempts)` |
| Permanent failure (invalid input, disabled address, unknown template, gate refused) | `state = 'failed'`, no retry |
| Attempts exhausted | `state = 'dead_letter'`, alert raised, operator review required |

`backoff(n) = min(2^n × 5s, 30min)` with ±20% jitter. `max_attempts` defaults to
8 and is set per job type.

Rules that hold for every job type:

- **A failed job never mutates the aggregate it was reporting on.** A failed
  email does not change the obligation; a failed render does not un-approve the
  draft; a failed OCR does not touch the original.
- **A failed job never leaves a partially visible artefact.** A render writes to
  object storage only after it succeeds, and a signed URL is issued only from a
  `rendered` row.
- **Dead-letter is a visible state, not a log line.** It surfaces on the
  operator dashboard and, for user-facing work, as an explicit failure state in
  the API (`api-conventions.md` §6).

## 5. Job type registry

| Job type | Trigger | Worker module | Lease | Notes |
| --- | --- | --- | --- | --- |
| `document.process` | `document.uploaded` | `workers/document_jobs.py` | 900s | Rasterise, classify, OCR ladder, extract |
| `document.rebuild-derivatives` | Operator | `workers/document_jobs.py` | 900s | Never touches the original |
| `research.compose-answer` | `ask` / `append_message` | `workers/research_jobs.py` | 300s | Emits resumable stream events |
| `export.render` | `export.requested` | `workers/export_jobs.py` | 600s | Re-verifies approval and hash before rendering |
| `report.render` | `report.requested` | `workers/export_jobs.py` | 600s | Supporting-document outputs (`export-service.md` §11) |
| `notification.deliver` | `obligation.reminder-due` and other notify events | `workers/notification_jobs.py` | 120s | Provider idempotency key = delivery id |
| `voice.finalise` | Session close | `workers/voice_jobs.py` | 300s | Persists recording and candidate transcript |
| `memory.ingest` | Any memory-relevant event | `workers/memory_jobs.py` | 60s | Non-authoritative; failure never blocks the publisher |
| `corpus.rebuild-index` | `corpus.release-published` | `workers/corpus_jobs.py` | 3600s | Builds per-audience index from the signed manifest |

## 6. Scheduled job registry

The scheduler owns exactly these. Each is idempotent, each records its last
successful run, and each is safe to run late.

| Schedule | Job | Owner | Purpose |
| --- | --- | --- | --- |
| every 5s | `outbox.drain` | platform | Move `pending` outbox rows to the queue |
| every 30s | `lease.reap` | platform | Return expired claims to `pending` |
| every 15m | `obligation.emit-reminders` | `obligations_service` | The `emit_due_reminders(as_of)` sweep |
| hourly | `billing.reconcile-subscriptions` | `billing_service` | Repair drift from missed webhooks |
| hourly | `export.expire` | `export_service` | Mark exports past `expires_at` |
| daily 02:00 Asia/Colombo | `storage.collect-orphans` | `document_service` | Blobs with no committed row, older than 24h |
| daily 02:30 Asia/Colombo | `retention.evaluate` | `retention_service` | Policy evaluation and `retention.review-due` |
| daily 03:00 Asia/Colombo | `memory.compact` | `memory_service` | Note reconsolidation and superseded-episode pruning |
| monthly, 1st 00:15 Asia/Colombo | `register.close-month` | `notarial_register_service` | Emits `register.monthly-period-closed` |

All wall-clock schedules are `Asia/Colombo`. A job that computes a legal date
does not use the scheduler's clock as the legal trigger; it uses the recorded
trigger event's timestamp.

## 7. Reconciliation sweeps

Three failure modes are unavoidable across a database and an object store, and
each has a named sweep rather than a hope:

| Failure | Sweep |
| --- | --- |
| Storage put succeeded, DB commit failed → orphan blob | `storage.collect-orphans`: delete blobs with no row, age > 24h, never under a legal hold |
| DB commit succeeded, enqueue failed | `outbox.drain` retries; the row was never lost because it was in the same transaction |
| Provider accepted, local persist failed | Idempotency key replay: re-send with the same key, provider returns the original result |

## 8. Observability contract

Every job emits, with no payload content:

- counters: claimed, succeeded, failed, dead-lettered, per job type;
- histograms: queue wait time, execution time, attempts to success;
- gauges: pending depth, oldest pending age, dead-letter depth, active leases.

Alert thresholds: pending depth or oldest-pending-age above the per-type budget,
any dead-letter arrival, and lease-reaper activity above baseline (which means
workers are crashing).

Logs carry `correlationId`, `causationId`, job type, and idempotency key. They
never carry payload bodies, transcript fragments, extracted values, or recipient
addresses.

## 9. Tests every job inherits

In `tests/integration/jobs/`, parameterised over the registry in §5:

1. Enqueue and state change commit atomically; a rollback leaves no outbox row.
2. Duplicate delivery of the same idempotency key produces exactly one effect.
3. A worker killed mid-job has its lease reaped and the job re-claimed once.
4. Retryable failure backs off; permanent failure does not retry.
5. Attempts exhausted lands in `dead_letter` and raises the alert.
6. A failed job leaves the source aggregate unchanged.
7. A failed job leaves no reachable partial artefact and no signed URL.
8. The scheduler elects one leader; a second replica idles and does not
   double-fire.
9. Every scheduled job is safe to run twice in the same window.
