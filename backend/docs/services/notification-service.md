# notification_service: implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`obligations-service.md`, `audit-service.md`, and `infrastructure.md`. One
markdown file is kept per service under `backend/docs/services/`.

This service belongs to the M3 backend foundation and the P1 reminder scope.
It is a module in the Draftly FastAPI backend, not a separately deployed
microservice in V0.

## 1. Decision

`obligations_service` decides that a reminder is due.
`notification_service` delivers that reminder through the allowed channels.

The boundary is:

```text
obligations_service
  owns what is due, when it is due, and who is responsible

notification_service
  owns delivery preferences, templates, attempts, retries, and provider state
```

An email failure must not roll back or otherwise change an obligation. The two
states remain independent:

```text
obligation state = overdue
notification delivery state = failed
```

## 2. What it owns

The service owns:

- notification preferences for each recipient and channel;
- rendering an approved message template from a template key and variables;
- delivery through email and in-app channels;
- delivery attempts, provider message ids, and final delivery state;
- retry and dead-letter behaviour;
- channel-level idempotency;
- privacy-safe notification previews; and
- notification delivery metrics and operational logs.

It does not own:

- obligation creation, due dates, status, or reminder eligibility;
- legal deadline calculation;
- matter, task, check, or workflow state;
- SMTP or provider-specific code inside the application layer;
- user or matter authorization;
- prescribed legal wording; or
- approval of reminder policy or message copy.

The service consumes a decision already made by the obligations module. It
must not independently recalculate whether a legal obligation is due.

## 3. Where it sits

```text
scheduled obligation sweep
          |
          v
obligations_service
          |
          | transactional outbox event
          v
obligation.reminder-due
          |
          v
application/notification_service.py
          |
          +--> NotificationPreferenceRepository
          +--> NotificationRepository
          +--> TemplateRepository
          +--> EmailPort
          +--> InAppNotificationPort
          +--> AuditPort
```

Suggested module layout:

```text
backend/src/draftly/
  application/
    obligations_service.py
    notification_service.py
  domain/
    obligations.py
    notifications.py
  ports/
    email.py
    notification_repository.py
    notification_preferences.py
    notification_templates.py
  infrastructure/
    email/
      console_adapter.py
      provider_adapter.py
  workers/
    obligation_reminder_jobs.py
    notification_jobs.py
```

The application service imports no FastAPI, SQLAlchemy, queue client, SMTP
library, or provider SDK. Infrastructure adapters implement those boundaries.

V0 uses the same FastAPI deployable, PostgreSQL database, transactional outbox,
and worker runtime as the rest of the backend. A separate notification
deployment is justified only after operational load or isolation requirements
make it necessary.

## 4. Event contract

The obligations module publishes one event when a configured reminder becomes
eligible:

```json
{
  "event": "obligation.reminder-due",
  "eventId": "evt-01K2DRAFTLY000000000001",
  "occurredAt": "2026-08-05T17:00:00+05:30",
  "obligationId": "obl-001",
  "matterId": "matter-synthetic-001",
  "recipientUserId": "user-synthetic-123",
  "dueAt": "2026-08-06T17:00:00+05:30",
  "reminderType": "due-in-24-hours",
  "templateKey": "obligation.reminder.due_in_24_hours",
  "correlationId": "corr-01K2DRAFTLY00000000001"
}
```

`matterId` is nullable because a notary licence renewal is user-scoped rather
than matter-scoped. Events contain identifiers and timing metadata only. They
must not contain client names, property details, document excerpts, extracted
facts, or other private matter content.

The event is written to the transactional outbox in the same transaction that
marks the reminder occurrence as emitted. This prevents both a lost event and
an obligation transaction that depends on successful email delivery.

## 5. Domain models

### 5.1 ReminderOccurrence

Owned by `obligations_service`:

```text
ReminderOccurrence
  id
  obligationId
  recipientUserId
  reminderType
  scheduledFor
  emittedAt?
  eventId?
```

Its uniqueness rule is:

```text
unique(obligationId, recipientUserId, reminderType)
```

This records which reminder decisions have already been emitted. It does not
record channel delivery.

### 5.2 NotificationPreference

Owned by `notification_service`:

```text
NotificationPreference
  userId
  channel = email | in-app
  enabled
  locale = en | si
  quietHoursStart?
  quietHoursEnd?
  timezone
  version
```

Mandatory service or compliance notices may need rules different from optional
product reminders. That policy must be approved before implementation; the
notification service must not invent it.

### 5.3 NotificationDelivery

```text
NotificationDelivery
  id
  sourceEventId
  obligationId
  matterId?
  recipientUserId
  channel
  reminderType
  templateKey
  locale
  status = queued | processing | delivered | failed | suppressed
  attemptCount
  nextAttemptAt?
  attemptedAt?
  deliveredAt?
  providerMessageId?
  failureCode?
  createdAt
  version
```

The delivery idempotency constraint is:

```text
unique(
  obligationId,
  recipientUserId,
  reminderType,
  channel
)
```

The source event id is also unique per consumed event. These two constraints
protect against both repeated event delivery and a worker retry sending the
same reminder twice.

## 6. Application flow

### 6.1 Emit a due reminder

`obligations_service` runs a scheduled, idempotent sweep:

```text
open obligation
  + reminder time has arrived
  + matching ReminderOccurrence does not exist
  -> create ReminderOccurrence
  -> write obligation.reminder-due to the outbox
  -> commit both
```

The initial configurable policy can support:

```text
due-in-7-days
due-in-1-day
due-today
overdue-by-1-day
overdue-by-7-days
```

These values are examples, not approved legal policy. The actual reminder
schedule must be configured and reviewed by the product and legal owners.

### 6.2 Consume the reminder event

```text
handle_reminder_due(event)
  1. validate the event schema and version
  2. reject or dead-letter an event with missing required identifiers
  3. load the recipient and current notification preferences
  4. determine the enabled channels
  5. create one NotificationDelivery per channel, idempotently
  6. mark disabled or unavailable channels as suppressed
  7. enqueue queued deliveries
```

Event acknowledgement occurs only after the delivery records are committed.
It does not wait for an external provider response.

### 6.3 Deliver a notification

```text
deliver_notification(delivery_id)
  1. claim the queued row with a lease
  2. re-check idempotency and terminal state
  3. load the approved template and recipient locale
  4. resolve the recipient address through the identity port
  5. render a privacy-safe subject and body
  6. call the channel port with the delivery id as idempotency key
  7. record delivered, retryable failure, or permanent failure
```

No email address is copied into the event. The worker resolves current contact
information at delivery time through an identity read port.

## 7. Port interfaces

The application-facing channel contract is:

```python
from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True)
class DeliveryResult:
    provider_message_id: str


class EmailPort(Protocol):
    async def send(
        self,
        *,
        recipient_address: str,
        template_key: str,
        locale: str,
        variables: Mapping[str, str],
        idempotency_key: str,
    ) -> DeliveryResult:
        ...
```

Provider adapters translate this contract into provider-specific requests.
Application and domain code never import the provider SDK.

V0 starts with a `console_adapter` that renders and stores synthetic or
development notifications without sending external email. A production
provider adapter is added only after secrets, data processing terms, delivery
region, bounce handling, and retention have been reviewed.

## 8. Templates, localization, and legal wording

Templates use stable keys and reviewed variables. They are versioned content,
not free-form strings assembled in a worker:

```text
templateKey = obligation.reminder.due_in_24_hours
variables = obligationLabelKey, dueAt, matterReference?, actionUrl
```

Requirements:

- English and Sinhala variants share the same template key and variable
  contract.
- Missing Sinhala copy falls back to English and remains explicitly marked for
  human translation review.
- Dates and times render in the recipient's timezone and locale.
- Matter references are synthetic in development and minimally identifying in
  production.
- Email subjects and lock-screen previews contain no client names, property
  addresses, identity numbers, deed numbers, or extracted facts.
- Prescribed legal wording and legal advice are prohibited in notification
  templates unless supplied and approved by the responsible lawyer.
- Template changes are versioned, reviewed, and auditable.

Frontend notification-center strings continue to use `next-intl`. Backend
email and push templates use their own versioned message catalogue because
they render outside the Next.js process.

## 9. Retry and failure policy

Failures are classified before retry:

| Failure | Handling |
| --- | --- |
| Timeout, rate limit, provider 5xx | Exponential backoff with bounded jitter |
| Invalid or disabled address | Permanent failure; do not retry |
| Recipient preference disabled | Suppressed; do not send |
| Duplicate event or delivery | Return existing delivery; do not send |
| Missing template or variables | Dead-letter and alert |
| Provider accepted message | Delivered; save provider message id |

Retries are bounded. After the configured maximum, the delivery becomes
`failed` and enters a dead-letter queue for operator review. A failed delivery
never mutates the obligation state.

The worker must support graceful retry after a crash between provider
acceptance and local persistence. Where the provider supports an idempotency
key, use the `NotificationDelivery.id`. Where it does not, reconciliation must
check the stored provider message id and provider event stream before any
manual resend.

## 10. Audit and observability

User-visible preference changes and material delivery outcomes emit audit
events without copying message bodies or private recipient data:

```text
notification.preference-changed
notification.delivered
notification.failed
notification.suppressed
```

Automated retries belong in operational logs and metrics rather than creating
one user-facing audit event per attempt.

Minimum metrics:

- reminders emitted by type;
- deliveries queued, delivered, failed, and suppressed by channel;
- retry count and time to delivery;
- dead-letter count;
- duplicate events suppressed; and
- provider latency and error class.

Logs use event, correlation, obligation, and delivery ids. They mask recipient
addresses and never include template bodies or matter content.

## 11. Security and privacy

- Resolve authorization and recipient ownership before emitting the reminder.
- Do not permit a caller to supply an arbitrary recipient address.
- Encrypt provider credentials and contact data at rest and in transit.
- Use least-privilege provider credentials and rotate them.
- Sign and verify provider webhooks; make webhook processing idempotent.
- Protect notification-preference routes with the authenticated user context.
- Keep action links short-lived and authenticated; never place private data in
  URL query parameters.
- Define retention separately for delivery metadata and provider payloads.
- Do not use production addresses in local, test, preview, or demo
  environments.

## 12. API surface

The event consumer and delivery worker are internal. The minimal user-facing
API is:

```text
GET   /api/v1/notification-preferences
PATCH /api/v1/notification-preferences
GET   /api/v1/notifications
POST  /api/v1/notifications/{id}/read
```

The in-app list is membership-scoped and paginated. A user can read or mark
their own notifications only. Delivery attempts and provider responses are
operator data and are not exposed through ordinary user routes.

There is no public "send email" endpoint in V0.

## 13. Invariants

| Invariant | Enforcement |
| --- | --- |
| Obligation and delivery state are independent | Reminder event is asynchronous; delivery failure never changes the obligation |
| Reminder decisions are made once | Unique ReminderOccurrence per obligation, recipient, and reminder type |
| Each channel sends at most once | Unique NotificationDelivery plus provider idempotency key |
| No private matter data enters events | Identifier-only event contract and schema tests |
| Preferences are respected | Preferences are checked before delivery creation |
| Provider code stays at the boundary | EmailPort and infrastructure adapters |
| Message copy is governed | Versioned template key and approved catalogue |
| Every material outcome is traceable | Correlation ids, delivery records, audit outcomes, and operational metrics |

## 14. Test list

### Unit

- A due reminder creates one ReminderOccurrence and one outbox event.
- Re-running the sweep does not emit the same reminder again.
- Preferences produce the correct queued and suppressed channels.
- Duplicate events return existing delivery rows.
- Retryable and permanent errors transition to the correct state.
- Rendering rejects missing template variables.
- Event and log serializers exclude private matter fields.

### Contract

- `obligation.reminder-due` schema and version compatibility.
- Notification preference and in-app notification API schemas.
- English and Sinhala template variable parity.
- Provider port contract and error classification.

### Integration

- Obligation transaction and outbox event commit or roll back together.
- Event consumption creates delivery rows before acknowledgement.
- Console adapter records a development delivery without external network use.
- Retry reaches delivered or dead-letter state without a duplicate send.
- Provider webhook updates the matching delivery idempotently.

### Security

- A user cannot read or change another user's preferences.
- A caller cannot choose an arbitrary delivery address.
- Cross-matter notification reads do not disclose another matter.
- Logs, audit rows, and events do not expose addresses or matter content.
- Unsigned or replayed provider webhooks are rejected.

## 15. V0 implementation sequence

1. Finalize the obligation scope and make `matterId` nullable for user-scoped
   duties.
2. Add ReminderOccurrence and the configurable reminder-policy model.
3. Add the transactional outbox event and idempotent consumer.
4. Add NotificationPreference and NotificationDelivery persistence.
5. Implement the console email adapter and in-app notifications.
6. Add the scheduled sweep, retry worker, dead-letter handling, and metrics.
7. Connect the frontend notification center and preferences.
8. Review privacy, retention, provider terms, approved templates, and legal
   policy before enabling an external email provider.

## 16. Decisions to confirm before coding

1. Keep notifications as a module in the existing FastAPI backend for V0.
2. Use the transactional outbox and the existing worker runtime.
3. Make `Obligation.matterId` nullable for user-scoped duties.
4. Store reminder decisions separately from channel delivery attempts.
5. Start with email and in-app channels; defer SMS and push.
6. Start with the console adapter; select an external provider only after the
   privacy and operational review.
7. Treat reminder schedules and message copy as governed configuration, not
   application constants.
8. Require provider idempotency where supported and retain the database
   uniqueness constraint regardless.
