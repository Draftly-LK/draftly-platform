"""Billing domain policies — transitions, restricted mode, feature catalogue."""

from __future__ import annotations

from datetime import datetime

from src.modules.billing.domain.models import PlanState, SubscriptionStatus

# Registered event names this service publishes (events.md §4).
EVENT_PAYMENT_FAILED = "billing.payment-failed"
EVENT_GRACE_PERIOD_ENDING = "billing.grace-period-ending"
EVENT_PLAN_CHANGED = "billing.plan-changed"
EVENT_SUBSCRIPTION_CANCELLED = "billing.subscription-cancelled"
EVENT_SUBSCRIPTION_RESTRICTED = "billing.subscription-restricted"
EVENT_TRIAL_ENDING = "billing.trial-ending"

# ISO 4217 codes are three letters; the plan's currency is data, not a domain
# constant, so only the shape is enforced here.
_CURRENCY_LENGTH = 3

# Controlled entitlement keys (billing-service.md §5.1). Unknown keys fail closed.
KNOWN_FEATURE_KEYS: frozenset[str] = frozenset(
    {
        "users.max",
        "active_matters.max",
        "document_processing.enabled",
        "document_pages.monthly",
        "research.enabled",
        "research_queries.monthly",
        "storage_bytes.max",
        "drafting.enabled",
        "export.enabled",
        "custom_templates.enabled",
        "whatsapp_notifications.enabled",
    }
)

# Features blocked in restricted mode (new paid consumption).
RESTRICTED_BLOCKED_FEATURES: frozenset[str] = frozenset(
    {
        "matter.create",
        "document_processing.enabled",
        "research.enabled",
        "drafting.enabled",
        "export.enabled",
        "whatsapp_notifications.enabled",
    }
)

# Map product feature gates to entitlement keys checked by require_feature.
FEATURE_TO_ENTITLEMENT: dict[str, str] = {
    "matter.create": "active_matters.max",
    "document_processing.enabled": "document_processing.enabled",
    "research.enabled": "research.enabled",
    "drafting.enabled": "drafting.enabled",
    "export.enabled": "export.enabled",
}

_ALLOWED_TRANSITIONS: dict[SubscriptionStatus, frozenset[SubscriptionStatus]] = {
    SubscriptionStatus.TRIALING: frozenset(
        {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.CANCELLED,
            SubscriptionStatus.EXPIRED,
        }
    ),
    SubscriptionStatus.ACTIVE: frozenset(
        {
            SubscriptionStatus.PAST_DUE,
            SubscriptionStatus.CANCELLED,
            SubscriptionStatus.EXPIRED,
        }
    ),
    SubscriptionStatus.PAST_DUE: frozenset(
        {
            SubscriptionStatus.GRACE_PERIOD,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.RESTRICTED,
        }
    ),
    SubscriptionStatus.GRACE_PERIOD: frozenset(
        {
            SubscriptionStatus.RESTRICTED,
            SubscriptionStatus.ACTIVE,
        }
    ),
    SubscriptionStatus.RESTRICTED: frozenset({SubscriptionStatus.ACTIVE}),
    SubscriptionStatus.CANCELLED: frozenset(
        {
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.ACTIVE,
        }
    ),
    SubscriptionStatus.EXPIRED: frozenset(),
}


def is_known_feature_key(feature_key: str) -> bool:
    return feature_key in KNOWN_FEATURE_KEYS


def can_transition(current: SubscriptionStatus, new: SubscriptionStatus) -> bool:
    if current == new:
        return True
    return new in _ALLOWED_TRANSITIONS.get(current, frozenset())


def subscription_allows_feature(status: SubscriptionStatus, feature_key: str) -> bool:
    """Restricted mode blocks new paid consumption but preserves read/billing access."""
    if status != SubscriptionStatus.RESTRICTED:
        return True
    entitlement = FEATURE_TO_ENTITLEMENT.get(feature_key, feature_key)
    return entitlement not in RESTRICTED_BLOCKED_FEATURES


def should_enter_grace(from_status: SubscriptionStatus) -> bool:
    return from_status in {SubscriptionStatus.PAST_DUE, SubscriptionStatus.ACTIVE}


def should_enter_restricted(from_status: SubscriptionStatus) -> bool:
    return from_status in {SubscriptionStatus.GRACE_PERIOD, SubscriptionStatus.PAST_DUE}


def restricted_mode_blocks(feature_key: str) -> bool:
    """True when restricted mode blocks this new paid operation.

    Reads of existing records, billing inspection, and downloads of already
    approved exports are not feature-gated at all, so they never reach here
    (billing-service.md §10).
    """
    entitlement = FEATURE_TO_ENTITLEMENT.get(feature_key, feature_key)
    return entitlement in RESTRICTED_BLOCKED_FEATURES


def is_stale_provider_event(
    event_occurred_at: datetime | None,
    provider_state_updated_at: datetime | None,
) -> bool:
    """True when a provider event describes state older than what is persisted.

    Out-of-order delivery must not regress the subscription
    (billing-service.md §7.3 step 7). An event with no provider timestamp is not
    treated as stale; it is applied under the transition rules instead.
    """
    if event_occurred_at is None or provider_state_updated_at is None:
        return False
    return event_occurred_at < provider_state_updated_at


def is_safe_return_path(return_path: str) -> bool:
    """A checkout return target must be a relative path inside the application.

    It is display-only — a redirect never grants entitlement — but it must not
    become an open redirect to an attacker's host.
    """
    if not return_path.startswith("/"):
        return False
    if return_path.startswith("//"):
        return False
    return not any(character in return_path for character in ("\\", "\n", "\r", "\t"))


def is_valid_money(currency: str, price_minor_units: int) -> bool:
    """Money is an integer count of minor units plus an ISO currency code.

    ``bool`` is rejected explicitly because it is an ``int`` subclass.
    """
    if isinstance(price_minor_units, bool) or not isinstance(price_minor_units, int):
        return False
    if price_minor_units < 0:
        return False
    return len(currency) == _CURRENCY_LENGTH and currency.isalpha() and currency.isupper()


def is_plan_mutable(state: PlanState) -> bool:
    """Only a draft plan version may be edited or activated."""
    return state == PlanState.DRAFT
