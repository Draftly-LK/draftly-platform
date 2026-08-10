"""Billing domain policies — transitions, restricted mode, feature catalogue."""

from __future__ import annotations

from src.modules.billing.domain.models import SubscriptionStatus

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
