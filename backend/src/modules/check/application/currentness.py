"""Positive scope membership evidence limits current work, never legal history."""

from src.modules.check.domain.models import CheckResult
from src.modules.matter.contracts import MatterScopeReadPort, MatterTransactionReference


async def read_current_transaction(
    scopes: MatterScopeReadPort | None, user_id: str, matter_id: str, transaction_id: str
) -> MatterTransactionReference | None:
    if scopes is None:
        return None
    try:
        transaction = await scopes.transaction(user_id, matter_id, transaction_id)
    except Exception:
        # An unavailable scope cannot establish detachment or clear stale work.
        return None
    if transaction is not None and (transaction.id, transaction.user_id, transaction.matter_id) == (
        transaction_id,
        user_id,
        matter_id,
    ):
        return transaction
    return None


def subject_is_detached(
    result: CheckResult, transaction: MatterTransactionReference | None
) -> bool:
    return (
        result.subject_id is not None
        and transaction is not None
        and result.transaction_id == transaction.id
        and result.subject_id not in transaction.parcel_subject_ids
        and all(role.subject_id != result.subject_id for role in transaction.party_roles)
    )
