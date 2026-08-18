# notification_service: implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`obligations-service.md`, `audit-service.md`, and `infrastructure.md`. One
markdown file is kept per service under `backend/docs/services/`.

This service belongs to the M3 backend foundation and the P1 reminder scope.
It is a module in the Draftly FastAPI backend, not a separately deployed
microservice in V0.

**Status:** L3 functional (V0 hardening, August 2026). React Email publication,
production domain verification, and approved product copy remain gated on human
review (see §15–§16).

## 1. Decision

`obligations_service` decides that a reminder is due.
`notification_service` delivers that reminder through the allowed channels.

The selected production email provider for V0 is **Resend**. Local development
and automated tests continue to use the console adapter and never send external
email.

All Draftly-authored email templates and reusable email components are owned by
`notification_service`. They are authored with **React Email**, versioned in
this repository, reviewed here, and published to Resend as deployment
artifacts. Resend delivers templates; it is not their source of truth.

The boundary is:

```text
obligations_service
  owns what is due, when it is due, and who is responsible

notification_service
  owns delivery preferences, every Draftly email template, reusable email
  components, attempts, retries, and provider state
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
- every Draftly-authored transactional email template;
- the React Email component library and email design tokens;
- template keys, variable schemas, versions, review, and publication;
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

Authentication, storage, or other providers may technically send an email, but
they do not own its Draftly-authored template. The approved source remains in
`notification_service` and is synchronized to that provider through a
documented deployment step. Any provider-controlled email that cannot follow
this process requires an explicit exception.

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
          +--> TemplateCatalog
          +--> TemplateDeploymentRepository
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
      resend_adapter.py
  workers/
    obligation_reminder_jobs.py
    notification_jobs.py
backend/email-templates/
  package.json
  src/
    components/
      email-layout.tsx
      email-header.tsx
      email-footer.tsx
      action-button.tsx
      status-callout.tsx
    templates/
      obligation-reminder.tsx
      restricted-action-required.tsx
    messages/
      en.json
      si.json
    manifest.ts
  tests/
  scripts/
    publish-resend.ts
```

The application service imports no FastAPI, SQLAlchemy, queue client, SMTP
library, React Email package, or provider SDK. Infrastructure adapters
implement those boundaries. The React Email package is a separate pnpm project
under the notification module and does not run inside the FastAPI process.

V0 uses the same FastAPI deployable, PostgreSQL database, transactional outbox,
and worker runtime as the rest of the backend. A separate notification
deployment is justified only after operational load or isolation requirements
make it necessary.

### 3.1 Resend provider decision

Draftly will use the Resend transactional Email API behind `EmailPort`:

```text
obligation.reminder-due
          |
          v
notification worker
          |
          v
ResendEmailAdapter
          |
          v
Resend Email API
          |
          v
recipient mail server
```

As verified on 31 July 2026, Resend's free transactional plan includes 3,000
emails per month and limits sending to 100 emails per day. These are provider
account limits, not domain rules or values to hardcode in Draftly. Production
configuration must expose the current quota and alert before either limit is
reached.

The intended sender is:

```text
Draftly <notifications@draftly.lk>
```

This address can be enabled only after the team controls `draftly.lk` and the
domain passes Resend's SPF and DKIM verification. DMARC should be configured
before production sending. Sender identity is environment configuration, not a
request field.

Provider choice rationale:

- a small transactional API suited to the FastAPI worker;
- verified-domain sending from a Draftly address;
- idempotency support for retry-safe sends;
- delivery, delay, failure, bounce, complaint, and suppression events;
- enough free capacity for development and a small controlled pilot; and
- no need to operate SMTP infrastructure in V0.

The free plan is not an availability guarantee. A quota breach or provider
outage must leave the delivery queued or failed visibly and must never change
the underlying obligation.

### 3.2 Template ownership and publication

The repository is authoritative:

```text
React Email source and message catalogue
          |
          | preview, lint, compatibility, snapshot, content approval
          v
approved template version
          |
          | CI publication
          v
published Resend Template
          |
          | template id or alias recorded against the version
          v
notification worker sends validated variables
```

Rules:

- Every Draftly-authored email lives under `backend/email-templates/`.
- Shared layout, header, footer, buttons, callouts, and typography are React
  Email components; templates compose them rather than duplicating markup.
- The repository owns template source, copy, variable schema, locale coverage,
  privacy classification, and approval state.
- Resend stores a published copy for runtime delivery. Direct dashboard edits
  are prohibited except emergency response; any emergency edit must be
  backported and reviewed immediately.
- Publishing is one-way from the reviewed repository version to Resend.
- A template deployment records environment, template key, locale, source
  version, Resend template id or alias, published by, and published at.
- Rollback selects an earlier published deployment. It never edits historical
  source or delivery records.
- Draft templates cannot be used by production delivery policies.

React Email is selected because it provides email-safe React components, local
preview, HTML rendering, plain-text rendering, compatibility checks, and
reusable TypeScript props. The planned packages are `react-email`,
`@react-email/components`, and their React peer dependencies. These are
justified email-template build dependencies and are added with pnpm only when
the template project is implemented.

## 4. Event contract

This service consumes the events listed in §8.1.1, all registered in
`events.md`. They share the envelope in `events.md` §2 and the same idempotent
consumer; only the template selection differs. The reminder event is shown in
full because it is the richest.

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
  "obligationClass": "legal-deadline",
  "urgency": "critical",
  "confidentialityLevel": "private-matter",
  "templateKey": "obligation.reminder.due_in_24_hours",
  "deliveryPolicyKey": "legal-deadline.standard",
  "correlationId": "corr-01K2DRAFTLY00000000001"
}
```

`matterId` is nullable because an annual notarial practice certificate is
user-scoped rather than matter-scoped. Events contain identifiers and timing
metadata only. They
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
  obligationClass
  urgency
  confidentialityLevel
  templateKey
  deliveryPolicyKey
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
  4. load the approved delivery policy for class, urgency, and confidentiality
  5. determine the permitted and enabled channels
  6. create one NotificationDelivery per channel, idempotently
  7. mark disabled or unavailable channels as suppressed
  8. enqueue queued deliveries
```

Event acknowledgement occurs only after the delivery records are committed.
It does not wait for an external provider response.

### 6.3 Deliver a notification

```text
deliver_notification(delivery_id)
  1. claim the queued row with a lease
  2. re-check idempotency and terminal state
  3. load the approved template manifest and recipient locale
  4. resolve the recipient address through the identity port
  5. validate variables against the template version's schema
  6. resolve the published template deployment for this environment
  7. call the channel port with the delivery id as idempotency key
  8. record delivered, retryable failure, or permanent failure
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
        template_version: str,
        locale: str,
        variables: Mapping[str, str],
        idempotency_key: str,
    ) -> DeliveryResult: ...
```

Provider adapters translate this contract into provider-specific requests.
Application and domain code never import the provider SDK.

V0 starts with a `console_adapter` that renders and stores synthetic or
development notifications without sending external email. Staging and
production use `ResendEmailAdapter` after secrets, data processing terms,
delivery region, bounce handling, and retention have been reviewed.

### 7.1 Resend adapter

The adapter calls `POST /emails` through the backend's existing `httpx`
dependency. No Resend SDK is required for V0.

Provider mapping:

```text
EmailPort.recipient_address -> to
configured sender           -> from
template deployment         -> template.id or template alias
validated variables         -> template.variables
NotificationDelivery.id     -> Idempotency-Key
provider response id         -> providerMessageId
```

The Resend adapter does not select, author, or edit templates. It resolves the
published deployment already selected by `notification_service` and sends its
identifier and variables. The Send Email request must not combine a Resend
Template with `html`, `text`, or `react`.

Resend retains idempotency keys for 24 hours. Draftly's database uniqueness
constraint remains the permanent duplicate-send guard; provider idempotency is
an additional protection for immediate retries.

Configuration:

```text
RESEND_API_KEY
RESEND_FROM_EMAIL=Draftly <notifications@draftly.lk>
RESEND_WEBHOOK_SECRET
```

Secrets are injected by the deployment environment and never committed,
returned by health endpoints, or written to logs.

## 8. Templates, components, localization, and legal wording

`notification_service` owns all Draftly email templates. Templates use stable
keys, typed React props, reviewed variables, and a versioned manifest. They are
not free-form strings assembled in a worker:

```text
templateKey = obligation.reminder.due_in_24_hours
templateVersion = 1.0.0
variables = obligationLabelKey, dueAt, matterReference?, actionUrl
locales = en, si
confidentiality = private-matter
approvalState = approved
```

Initial English copy for content review:

```text
Subject: Draftly deadline reminder

Matter DFT-SYN-2026-014 (synthetic) has an obligation due on 6 August.
Log in to Draftly to review it.
```

This is product copy, not a provider-side hardcoded template. The approved
English and Sinhala versions live in Draftly's versioned message catalogue.

Requirements:

- Templates use React Email components from the notification-owned component
  library.
- Template props and runtime variable schemas must match exactly.
- Each template renders both email-safe HTML and a meaningful plain-text
  alternative.
- Email styling uses a small email-safe projection of Draftly's design tokens;
  it does not import workspace CSS or depend on unsupported browser layout.
- Email components use semantic structure, useful preview text, descriptive
  links, and sufficiently large text and tap targets.
- Sinhala templates preserve Unicode text, use robust system-font fallbacks,
  and use a tested line height; delivery must not depend on a remote custom
  font loading successfully.
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
- Template changes are versioned, visually reviewed, and auditable.
- No template may access a matter or user repository directly. The application
  service supplies only validated, privacy-classified variables.

Frontend notification-center strings continue to use `next-intl`. Backend
email templates use their own notification-owned React Email message catalogue
because they render outside the Next.js process.

### 8.1 Initial template inventory

All Draftly-authored transactional email categories use this same ownership
model:

```text
obligations
  - upcoming deadline
  - due today
  - overdue
  - escalation

matter collaboration
  - assignment
  - review requested
  - comment or mention

documents and processing
  - processing failed
  - replacement ready for review
  - registered document ready for collection

drafts and approvals
  - draft review requested
  - approval recorded
  - export ready

account
  - invitation

restricted compliance
  - neutral action required
```

Email verification, magic links, login codes, account recovery, password
changes, and sign-in security notices are **not** in this inventory. Clerk owns
them (`auth-service.md` §2). An earlier version of this list included them,
which contradicted that rule; only the invitation stays here, because an
invitation is a Draftly product event rather than an authentication token.

The inventory describes product events, not approved final copy. Templates are
implemented only when their owning workflow exists.

### 8.1.1 Every template needs a registered trigger event

A template with no publisher is dead copy. Each category above maps to an event
in `events.md`; this service consumes them all through the same idempotent
handler as `obligation.reminder-due`:

| Template category | Trigger event |
| --- | --- |
| Upcoming deadline, due today, overdue | `obligation.reminder-due` |
| Escalation | `obligation.escalated` |
| Deadline confirmed or corrected | `obligation.deadline-confirmed`, `obligation.deadline-corrected` |
| Assignment | `matter.membership-changed`, `matter.assigned-notary-changed` |
| Review requested | `workflow.review-requested`, `draft.review-requested` |
| Workflow setup failed | `workflow.setup-failed` |
| Signing appointment | `workflow.signing-scheduled` |
| Processing failed | `document.processing-failed` (terminal only) |
| Replacement ready for review | `document.replaced` |
| Registered document ready for collection | `instrument.collection-ready` |
| Approval recorded | `draft.approved` |
| Approval invalidated | `draft.approval-invalidated` |
| Export ready | `export.rendered` |
| Export failed | `export.failed` (terminal only) |
| Invitation | `user.invited` |
| Billing notices | `billing.*` (`events.md` §5.12) |
| Restricted action required | `party.designated-person-confirmed`, restricted `obligation.reminder-due` |

Comment and mention notifications have no publisher because Draftly has no
commenting feature. That template is deferred until one exists, rather than
carried as an unreachable entry.

### 8.2 Restricted compliance notifications

Sanctions and suspicious-transaction workflows use
`restricted-compliance`. The notification service applies a dedicated
delivery policy before user preferences:

```text
recipient
  = compliance officer or explicitly approved backup role

in-app destination
  = authenticated restricted compliance workspace

email or push content
  = neutral action-required message only
```

The event, subject, preview, body, logs, metrics, and provider metadata must
not contain:

- the client or beneficial-owner name;
- the designated-list match;
- a suspicion narrative;
- the matter reference;
- property or deed details; or
- the existence or contents of an STR.

Preference settings cannot redirect restricted notifications to an arbitrary
address. Whether a mandatory compliance alert may bypass an ordinary opt-out
is a governed legal and firm-policy decision, not an application default.

## 9. Retry and failure policy

Failures are classified before retry:

| Failure | Handling |
| --- | --- |
| Timeout, rate limit, provider 5xx | Exponential backoff with bounded jitter |
| Invalid or disabled address | Permanent failure; do not retry |
| Recipient preference disabled | Suppressed; do not send |
| Duplicate event or delivery | Return existing delivery; do not send |
| Missing template or variables | Dead-letter and alert |
| Template is draft, retired, or unpublished | Dead-letter; never fall back to another template |
| Resend quota or rate limit | Retry after provider window; alert before exhaustion |
| Provider accepted message | Delivered; save provider message id |

Retries are bounded. After the configured maximum, the delivery becomes
`failed` and enters a dead-letter queue for operator review. A failed delivery
never mutates the obligation state.

The worker must support graceful retry after a crash between provider
acceptance and local persistence. The Resend adapter sends the
`NotificationDelivery.id` as its idempotency key. Draftly must retry the same
payload with the same key; changing a payload under an existing key is an
error.

### 9.1 Resend delivery webhooks

The webhook handler consumes the delivery events needed by V0:

```text
email.sent
email.delivered
email.delivery_delayed
email.failed
email.bounced
email.complained
email.suppressed
```

`email.sent` means the API request was accepted. `email.delivered` means the
recipient's mail server accepted the message; it does not prove that a person
read it. Draftly records these states separately.

The handler verifies the Resend webhook signature with
`RESEND_WEBHOOK_SECRET`, stores each provider event idempotently, and maps the
provider email id back to `NotificationDelivery.providerMessageId`.

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
- Restrict the Resend API key to the notification worker environment.
- Verify `draftly.lk` through SPF and DKIM and publish a reviewed DMARC policy
  before production sending.
- Restrict non-production Resend delivery to an explicit synthetic-recipient
  allowlist.
- Protect notification-preference routes with the authenticated user context.
- Apply a separate role allowlist to restricted-compliance notifications;
  ordinary matter membership is insufficient.
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
| Restricted alerts reveal no sensitive context | Dedicated delivery policy, neutral template, and compliance-role allowlist |
| Preferences are respected | Preferences are checked before delivery creation |
| Provider code stays at the boundary | EmailPort and infrastructure adapters |
| Every notification is organisation-scoped | Preferences, deliveries, and the in-app list filter on `ctx.organisationId` before the recipient |
| Paid channels are metered | Email and in-app are included; SMS and WhatsApp, when added, pass `require_feature` and `reserve_usage` per message before send |
| Message copy is governed | Notification-owned React Email source, typed variables, approval, and one-way publication |
| Every material outcome is traceable | Correlation ids, delivery records, audit outcomes, and operational metrics |

## 14. Test list

### Unit

- A due reminder creates one ReminderOccurrence and one outbox event.
- Re-running the sweep does not emit the same reminder again.
- Preferences produce the correct queued and suppressed channels.
- Duplicate events return existing delivery rows.
- Retryable and permanent errors transition to the correct state.
- Rendering rejects missing template variables.
- Draft, retired, or unpublished template versions cannot send.
- Every React Email template renders HTML and plain text for both locales.
- Shared components render consistently across every template.
- Event and log serializers exclude private matter fields.
- Restricted-compliance policy produces only a neutral message for approved
  recipients.

### Contract

- `obligation.reminder-due` schema and version compatibility.
- Notification preference and in-app notification API schemas.
- English and Sinhala template variable parity.
- React Email prop, manifest, and runtime variable-schema parity.
- Provider port contract and error classification.
- Resend request mapping, 24-hour idempotency behaviour, and webhook schemas.

### Integration

- Obligation transaction and outbox event commit or roll back together.
- Event consumption creates delivery rows before acknowledgement.
- Console adapter records a development delivery without external network use.
- Approved React Email versions publish to the expected Resend template
  deployment; draft versions do not publish.
- Resend adapter tests use mocked HTTP responses and never send real email.
- Retry reaches delivered or dead-letter state without a duplicate send.
- Signed Resend webhook updates the matching delivery idempotently.

### Security

- A user cannot read or change another user's preferences.
- A caller cannot choose an arbitrary delivery address.
- Cross-matter notification reads do not disclose another matter.
- Ordinary matter members cannot discover restricted-compliance
  notifications.
- Logs, audit rows, and events do not expose addresses or matter content.
- Unsigned or replayed provider webhooks are rejected.

## 15. V0 implementation sequence

1. Finalize the obligation scope and make `matterId` nullable for user-scoped
   duties.
2. Add ReminderOccurrence and the configurable reminder-policy model.
3. Add the transactional outbox event and idempotent consumer.
4. Add NotificationPreference and NotificationDelivery persistence.
5. Scaffold the notification-owned React Email project, shared components,
   bilingual catalogue, manifest, preview, and rendering tests.
6. Implement and approve the first obligation and restricted-action templates.
7. Add one-way publication to Resend Templates and deployment records.
8. Implement the console email adapter and in-app notifications.
9. Implement `ResendEmailAdapter` over `httpx` with mocked contract tests.
10. Verify the sending domain and configure SPF, DKIM, and DMARC.
11. Add signed Resend webhooks, the scheduled sweep, retry worker, dead-letter
   handling, quota alerts, and delivery metrics.
12. Connect the frontend notification center and preferences.
13. Review privacy, retention, Resend's data processing terms, approved
    templates, and legal policy before enabling production email.

## 16. Decisions to confirm before coding

1. Keep notifications as a module in the existing FastAPI backend for V0.
2. Use the transactional outbox and the existing worker runtime.
3. Make `Obligation.matterId` nullable for user-scoped duties.
4. Store reminder decisions separately from channel delivery attempts.
5. Start with email and in-app channels; defer SMS and push.
6. Use the console adapter locally and Resend for staging and production email.
7. Keep every Draftly-authored email template and component under
   `notification_service`; the repository is the source of truth.
8. Send `NotificationDelivery.id` as the Resend idempotency key and retain the
   database uniqueness constraint as the permanent guard.
9. Add a restricted-compliance delivery policy with neutral templates and a
   dedicated role allowlist before enabling AML/CFT alerts.
10. Author templates with React Email and publish approved versions one-way to
    Resend Templates; do not add a Node runtime to FastAPI.

## 17. Provider references

- [Resend pricing](https://resend.com/docs/knowledge-base/what-is-resend-pricing)
- [Resend domain verification](https://resend.com/docs/dashboard/domains/introduction)
- [Resend send-email API and idempotency header](https://resend.com/docs/api-reference/emails/send-email)
- [Resend webhook event types](https://resend.com/docs/webhooks/event-types)
- [React Email components](https://react.email/components)
- [React Email rendering](https://react.email/docs/utilities/render)
- [Publishing React Email templates to Resend](https://resend.com/docs/knowledge-base/template-emails-with-react-email)
