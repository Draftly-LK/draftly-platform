# billing_service: implementation design

Companion to `backend/backend-implementation-plan-v0.md`,
`auth-service.md`, `matter-service.md`, `notification-service.md`, and
`audit-service.md`. One markdown file is kept per service under
`backend/docs/services/`.

## 1. Decision

Draftly subscriptions belong to the **User** (solo notary account), not to a
separate organisation workspace and not directly to a `Matter`.

```text
User
  +-- Matters
  +-- Documents
  +-- Subscription
```

V0 is **solo only**: one verified Gmail account, one subscription, no seats
and no multi-org billing. Firm or multi-seat plans remain product data for a
later release; they do not imply an `Organisation` entity in auth.

`billing_service` is a separate logical service inside the FastAPI backend:

```text
auth_service
  = who is the actor, what role do they hold, and what may they do?

billing_service
  = which plan and payment state apply to that user, which product
    capabilities are entitled, and which quotas remain?
```

Both authorisation and entitlement gates must pass. A paid plan never grants a
role, and an authorised role never bypasses a plan or quota.

## 2. What it owns

The service owns:

- immutable plan versions and their entitlements;
- user subscriptions and normalized payment state;
- provider customer and subscription references;
- usage ledgers and period aggregates;
- checkout and customer-portal orchestration;
- verified, idempotent billing-webhook processing;
- grace-period and restricted-mode decisions; and
- billing history, audit events, and notification events.

It does not own:

- login, identity sessions, or account roles;
- matter membership or legal-workflow permission;
- card numbers, bank credentials, or provider payment tokens;
- ordinary application-email delivery;
- legal records, uploaded evidence, drafts, approvals, or exports; or
- deletion and retention policy for legal files.

The payment provider hosts or tokenises payment credentials. Draftly stores
only the references and state needed to reconcile billing.

## 3. User boundary

`auth_service` establishes the actor through `RequestContext.actor_id`. Every
customer row, including `Subscription` and usage ledgers, carries **`userId`**
equal to that owning account.

Every `Matter` carries `owner_user_id` (and the same `user_id` tenancy key on
related rows). Every billing command scopes to `ctx.actor_id`; it never accepts
a trusted `userId` from a request body or payment-success page.

Subscription and usage state remain server-side and are not embedded in
identity tokens because they can change while a session is active.

## 4. Where it sits

```text
authenticated product request
        |
        +--> auth_service.authorize(ctx, capability, matter_id?)
        |
        +--> billing_service.require_feature(user_id, feature)
        |
        +--> billing_service.reserve_or_consume(user_id, metric)
        |
        v
   product service performs operation

provider checkout
        |
        v
POST /api/v1/billing/webhooks/payhere
        |
        v
billing_service verifies checksum/signature and event identity
        |
        +--> subscription repository
        +--> billing webhook-event repository
        +--> audit outbox
        +--> notification outbox
```

API routers parse requests and preserve the raw webhook body. They do not
grant entitlements. The application service imports no FastAPI or provider SDK.

## 5. Domain models

### 5.1 Plan and entitlements

```text
PlanVersion
  id
  code                  # trial-v1 | solo-v1 | firm-v1
  family                # trial | solo | firm
  name
  version
  billingInterval       # trial | monthly | yearly
  currency
  priceMinorUnits
  state                 # draft | active | retired
  effectiveFrom
  effectiveTo?

PlanEntitlement
  planVersionId
  featureKey
  limitValue?
  enabled
```

Published plan versions are immutable. A price or allowance change creates a
new version; it does not silently rewrite an existing subscriber's agreement.
Money is stored as integer minor units with an ISO currency code, never as a
floating-point value.

Example entitlement keys:

```text
users.max
active_matters.max
document_processing.enabled
document_pages.monthly
research.enabled
research_queries.monthly
storage_bytes.max
drafting.enabled
export.enabled
custom_templates.enabled
whatsapp_notifications.enabled
```

Keys are a controlled catalogue. Unknown keys fail closed.

### 5.2 Subscription

```text
Subscription
  id
  userId
  planVersionId
  provider
  providerCustomerId
  providerSubscriptionId
  status
  currentPeriodStart
  currentPeriodEnd
  trialEndsAt?
  cancelAtPeriodEnd
  gracePeriodEndsAt?
  providerStateUpdatedAt
  createdAt
  updatedAt
  version
```

Normalized statuses are:

```text
trialing | active | past_due | grace_period | restricted | cancelled | expired
```

Provider-specific states remain adapter data. The domain maps them to the
normalized states above. `cancelAtPeriodEnd=true` does not revoke access before
the paid period ends.

### 5.3 Usage

Use an append-only ledger for retry safety and a rebuildable aggregate for
fast reads:

```text
UsageLedgerEntry
  id
  userId
  metric
  quantity
  periodStart
  periodEnd
  operationId
  state                 # reserved | consumed | released
  createdAt

UsageAggregate
  userId
  metric
  quantity
  periodStart
  periodEnd
  updatedAt
  version
```

`operationId` is unique within a user and metric. Retrying the same
OCR, research, rendering, or notification job therefore cannot consume quota
twice. Quota checks and reservations are atomic to prevent concurrent requests
from overspending the same remaining allowance.

`reserve_usage`, `consume_usage`, and `release_usage` acquire the usage
repository's user-wide transaction lock before reading ledger or aggregate
state. PostgreSQL holds this advisory lock through the caller's transaction
commit or rollback; repeated acquisition in that same transaction is safe.
Different idempotency keys and different quota consumers share the lock for
one user. Product-specific request locks do not replace this billing lock.

When exact usage is unknown before work starts, reserve a conservative amount,
then finalize actual usage or release the reservation. For example, document
upload may reserve the validated page count before starting OCR.

### 5.4 Webhook event

```text
BillingWebhookEvent
  id
  provider
  providerEventId
  eventType
  receivedAt
  providerOccurredAt?
  processedAt?
  processingState       # received | processed | ignored | failed
  payloadHash
  failureCode?
```

`(provider, providerEventId)` is unique. If a provider does not supply a stable
event identifier, the adapter derives a documented deterministic idempotency
key from stable payment identifiers and the payload hash. Raw payloads are not
written to ordinary logs. Retain an encrypted raw event only when reconciliation
requires it and the approved retention policy permits it.

## 6. Ports

```python
class BillingProviderPort(Protocol):
    async def create_checkout(self, command: CheckoutCommand) -> Checkout: ...
    async def create_customer_portal(self, customer_id: str) -> Portal: ...
    async def cancel_subscription(self, subscription_id: str) -> None: ...
    async def reactivate_subscription(self, subscription_id: str) -> None: ...
    async def verify_webhook(self, request: RawWebhook) -> ProviderEvent: ...
    async def fetch_subscription(self, subscription_id: str) -> ProviderSubscription: ...
```

Repository and integration ports:

- `PlanRepository` loads immutable plan versions and entitlements.
- `SubscriptionRepository` loads and updates user subscriptions with optimistic
  concurrency.
- `UsageRepository` reserves, consumes, releases, and aggregates usage
  atomically.
- `BillingWebhookEventRepository` claims provider events idempotently.
- `UserReadPort` confirms the user account exists and is active for billing.
- `AuditPort` records plan, subscription, payment-state, and admin changes.
- `EventPort` emits notification events through the transactional outbox.
- `ClockPort` makes period and grace calculations deterministic in tests.

V0 infrastructure implements `BillingProviderPort` in
`infrastructure/billing/payhere_adapter.py`. Later adapters may implement Lemon
Squeezy or Paddle without changing application or domain code.

## 7. Application methods

### 7.1 Reads and checkout

```text
list_plans(ctx) -> list[PlanRead]
get_subscription(ctx) -> SubscriptionRead
get_usage(ctx) -> list[UsageRead]
create_checkout(ctx, plan_version_id, return_path) -> CheckoutRead
create_customer_portal(ctx) -> PortalRead
cancel_subscription(ctx) -> SubscriptionRead
reactivate_subscription(ctx) -> SubscriptionRead
```

Only active, publicly offered plan versions appear in `list_plans`. Checkout
validates that the actor holds `billing.manage`, creates or reuses the provider
customer idempotently, and supplies only server-approved price and return data
to the adapter. A return URL displays status but never changes the subscription.

### 7.2 Entitlement and quota gates

```text
require_feature(user_id, feature_key) -> EntitlementDecision
reserve_usage(user_id, metric, quantity, operation_id) -> Reservation
consume_usage(reservation_id, actual_quantity) -> UsageRead
release_usage(reservation_id) -> UsageRead
```

Product services call these gates server-side. Typical order:

```text
auth_service.authorize(ctx, capability, matter_id)
billing_service.require_feature(ctx.actor_id, feature)
billing_service.reserve_usage(ctx.actor_id, metric, quantity, job_id)
perform or enqueue operation
consume actual usage, or release reservation on terminal failure
```

Frontend button visibility is only presentation. It is never an entitlement
control.

### 7.3 Webhook handling

```text
handle_webhook(provider, raw_request) -> WebhookReceipt
```

1. Verify the checksum or signature over the unmodified provider payload.
2. Normalize the event and claim its provider event id.
3. Return success without repeating work when the event was already processed.
4. Resolve the subscription through trusted provider identifiers.
5. Reject or ignore events that cannot map to one user safely.
6. Apply only valid state transitions with optimistic concurrency.
7. Ignore stale out-of-order state, or reconcile from the provider when order
   is ambiguous.
8. Write the subscription update, event state, audit event, and outbox events
   in one transaction.
9. Acknowledge only after durable processing or durable retry scheduling.

The browser redirect from checkout is not evidence of payment. Premium access
is granted only after verified provider state is persisted.

## 8. V0 plans and charging model

Launch with three plan families only:

| Plan | Intended boundary |
| --- | --- |
| Trial | Solo account, a small matter/page/research allowance, and a fixed trial period |
| Solo | One notary account, normal matter and processing allowances, drafting, export, and email reminders |
| Firm | Reserved plan family for a future multi-seat release; not an organisation entity in V0 auth |

Use **base subscription + included usage + optional overage or add-ons**.
V0 Solo has no seat metering. Usage metrics represent OCR, LLM/research, object storage,
rendering, SMS, or WhatsApp costs. Exact prices, limits, trial duration, and
overage policy are product decisions stored as plan data, not hardcoded in
application services.

## 9. Payment provider decision

Use **PayHere for the first Sri Lankan release** and keep the domain
provider-neutral. PayHere supports recurring payments on eligible plans and
local LKR checkout. Provider onboarding, settlement, limits, fees, and
currencies must be rechecked before launch; these commercial facts must not be
encoded as domain invariants.

For a later international release, assess Lemon Squeezy or Paddle as
Merchant-of-Record options. They can own international tax collection and
billing obligations at a higher commercial cost. Stripe's published global
availability page did not list Sri Lanka as a directly supported business
country when this decision was reviewed, so do not assume a Sri Lankan entity
can open a direct Stripe account.

Provider facts and links in section 16 were reviewed on **2026-07-31**. They
are operational inputs, not permanent architecture facts.

## 10. Payment failure and restricted mode

Default transition:

```text
payment failure
  -> past_due
  -> 7-14 day configured grace_period
  -> restricted
```

Restricted mode preserves access to legal records:

- view existing matters and documents;
- view and download existing approved exports;
- inspect billing state;
- update payment details; and
- cancel or reactivate the subscription.

It may block new paid consumption:

- creating new matters;
- uploading or processing new documents;
- running OCR or AI extraction;
- asking new research questions;
- creating new drafts or exports; and
- sending paid SMS or WhatsApp notifications.

Payment failure never immediately deletes or hides the user's legal records.
Retention and eventual account closure follow the separately approved
legal-data policy.

## 11. API surface

```http
GET  /api/v1/billing/plans
GET  /api/v1/billing/subscription
GET  /api/v1/billing/usage

POST /api/v1/billing/checkout
POST /api/v1/billing/customer-portal
POST /api/v1/billing/cancel
POST /api/v1/billing/reactivate

POST /api/v1/billing/webhooks/payhere

POST /api/v1/admin/plans
POST /api/v1/admin/plans/{id}/activate
POST /api/v1/admin/subscriptions/{id}/grant-trial
```

Billing reads and customer commands require an authenticated actor with
`billing.manage` (granted to `approver` and `administrator` in V0). Provider
webhook routes do not use user authentication; they require provider
verification, strict body limits, rate limiting, and idempotency. Plan
administration requires `platform.administer`, distinct from account
`administrator`.

## 12. Notifications and audit

`billing_service` emits state events; `notification_service` owns delivery:

```text
billing.trial-ending
billing.payment-failed
billing.grace-period-ending
billing.plan-changed
billing.subscription-cancelled
```

The audit trail records actor-initiated checkout, plan, cancellation,
reactivation, and administrative changes, plus provider-originated state
changes. It stores provider references and normalized before/after state, not
card details or authentication material.

## 13. Invariants

| Invariant | Enforcement |
| --- | --- |
| Subscription belongs to user | `Subscription.userId` is required and unique for the current subscription boundary |
| Tenant isolation precedes billing | `user_id` comes from `RequestContext.actor_id` |
| Payment does not grant permission | Auth role and matter checks run independently of entitlements |
| Permission does not grant a paid feature | Product services enforce feature and quota server-side |
| Browser redirects are untrusted | Only verified provider events update payment state |
| Webhooks are replay-safe | Unique provider event id and transactional processing |
| Usage is retry-safe | Unique operation id and append-only reservation/consumption ledger |
| Published plans are immutable | Price or entitlement changes create a new plan version |
| Legal records survive payment failure | Grace and restricted modes preserve existing records and approved exports |
| Payment data stays outside Draftly | Hosted/tokenized checkout; no card or bank credential storage |

## 14. Failure modes

- Duplicate webhook: return success after confirming the recorded result.
- Invalid checksum or signature: reject without revealing subscription data.
- Out-of-order event: ignore stale state or reconcile from the provider API.
- Provider timeout after checkout creation: retry with the same idempotency key.
- Unknown provider subscription: quarantine the event for operator review; do
  not create a user from webhook data.
- Concurrent quota requests: serialize or use an atomic conditional update.
- Worker fails before consumption: release reservation only on terminal
  failure; retain it while a retry is possible.
- Plan retired during checkout: reject before provider checkout creation.
- Payment fails during legal work: let already accepted work reach a safe
  persisted state; apply restricted mode to the next new paid operation.
- Billing provider unavailable: retain current persisted entitlement until the
  configured reconciliation policy decides otherwise; do not guess a state.

## 15. Test list

- **Unit:** plan-version immutability; normalized status transitions; grace and
  restricted policy; feature denial; seat and usage limits; reservation,
  consumption, release, and retry idempotency.
- **Contract:** billing read schemas; checkout command; normalized provider
  events; raw webhook verification contract; stable entitlement keys.
- **Integration:** PayHere checkout and webhook fixtures; duplicate and
  out-of-order events; provider reconciliation; transactionally coupled
  subscription, webhook, audit, and outbox writes.
- **Security:** cross-user billing access; forged user id;
  forged success redirect; invalid webhook checksum; oversized payload; log and
  audit inspection for payment secrets.
- **End-to-end:** trial provisioning, Solo purchase, renewal, failed payment,
  grace, restricted read access, reactivation, cancellation at period end, and
  restoration without loss of legal records.

## 16. Decisions and references

Closed for V0:

- subscription owner: **user (solo account)**;
- service boundary: **separate `billing_service`**;
- initial provider adapter: **PayHere**;
- plan families: **Trial, Solo, Firm**; and
- charging model: **base plan with included usage**.

Confirm before production coding:

1. Legal organisation and bank account used for PayHere onboarding.
2. Exact plan prices, currencies, allowances, taxes, and refund policy.
3. Trial duration and whether a payment method is required.
4. Grace-period length and the exact restricted-mode capability matrix.
5. Overage purchase, hard-stop, and quota-reset rules.
6. Webhook retention, reconciliation, and operator-dispute procedures.
7. Whether V0 needs a provider-hosted customer portal or Draftly-owned billing
   management actions.

Provider documentation:

- [PayHere limits and fees][payhere-fees]
- [PayHere Recurring API][payhere-recurring]
- [Lemon Squeezy supported countries][lemon-countries]
- [Lemon Squeezy pricing][lemon-pricing]
- [Paddle as Merchant of Record][paddle-mor]
- [Stripe global availability][stripe-global]
- [Stripe subscription webhooks][stripe-webhooks]

[payhere-fees]: https://support.payhere.lk/limits-and-fees
[payhere-recurring]: https://support.payhere.lk/api-%26-mobile-sdk/recurring-api
[lemon-countries]: https://docs.lemonsqueezy.com/help/getting-started/supported-countries
[lemon-pricing]: https://www.lemonsqueezy.com/pricing
[paddle-mor]: https://developer.paddle.com/get-started/how-paddle-works/
[stripe-global]: https://stripe.com/global
[stripe-webhooks]: https://docs.stripe.com/billing/subscriptions/webhooks
