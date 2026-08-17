"""Translate the confirmed fact tier into the eligibility gates' input.

This adapter is where "we have not looked at that yet" is kept distinct from
"the answer is no". Every mapping below defaults to ``UNKNOWN`` or to the
``NO_EVIDENCE_REVIEWED`` member of its vocabulary when no confirmed fact exists,
so a missing fact leaves the predicate unmet instead of quietly satisfying it
(§4.4, §6.4).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.content_governance.contracts import (
    EncumbranceStatus,
    NoticeStatus,
    OccupationStatus,
    TriState,
)
from src.modules.matter.domain.routing import MatterFactSnapshot
from src.modules.verification.contracts import ConfirmedFactReadPort, FactTierSummary
from src.modules.verification.infrastructure.repository import SqlConfirmedFactReader

FACT_TRANSFEROR_IS_OWNER = "rta.party.transferor_is_registered_owner"
FACT_TITLE_CERTIFICATE = "rta.title.certificate_no"
FACT_TRANSMISSION_COMPLETED = "rta.process.transmission_completed"
FACT_LIFE_INTEREST = "rta.interest.life_interest_present"
FACT_SPECIAL_CONDITION = "rta.instrument.special_condition_present"
FACT_COOWNERS = "rta.party.coowners_present"
FACT_CREATES_COOWNERSHIP = "rta.party.creates_coownership"
FACT_MORTGAGE_STATUS = "rta.interest.mortgage_status"
FACT_LEASE_STATUS = "rta.interest.lease_status"
FACT_OCCUPATION_STATUS = "rta.interest.occupation_status"
FACT_NOTICE_STATUS = "rta.interest.caveat_or_notice_status"
FACT_COURT_PROCEEDING = "rta.process.court_proceeding_reference"
FACT_MORTGAGE_REFERENCE = "rta.interest.mortgage_reference"
FACT_MORTGAGEE_AUTHORITY = "rta.interest.mortgagee_authority_confirmed"
FACT_DISCHARGE_EVIDENCE = "rta.interest.discharge_evidence_kind"

#: Discharge evidence kinds that are, on their own, not enough. Which of the
#: remaining kinds suffices is a lawyer-validation question (§16.1 item 8), so
#: nothing here treats any single document as conclusive without confirmation.
_INSUFFICIENT_DISCHARGE = frozenset({"NONE", "PAYMENT_RECEIPT_ONLY"})


def _tri(summary: FactTierSummary, fact_type_id: str) -> TriState:
    """A confirmed boolean or tri-state fact; UNKNOWN when nothing is confirmed."""
    entry = summary.confirmed.get(fact_type_id)
    if entry is None:
        return TriState.UNKNOWN
    return _coerce_tri(entry.value)


def _coerce_tri(value: Any) -> TriState:
    if isinstance(value, bool):
        return TriState.YES if value else TriState.NO
    text = str(value).upper()
    try:
        return TriState(text)
    except ValueError:
        # A present-but-unrecognised value is not a "no". It is a review task,
        # which UNKNOWN produces.
        return TriState.UNKNOWN


def _encumbrance(summary: FactTierSummary, fact_type_id: str) -> EncumbranceStatus:
    entry = summary.confirmed.get(fact_type_id)
    if entry is None:
        return EncumbranceStatus.NO_EVIDENCE_REVIEWED
    try:
        return EncumbranceStatus(str(entry.value))
    except ValueError:
        return EncumbranceStatus.NO_EVIDENCE_REVIEWED


def _occupation(summary: FactTierSummary) -> OccupationStatus:
    entry = summary.confirmed.get(FACT_OCCUPATION_STATUS)
    if entry is None:
        return OccupationStatus.NO_EVIDENCE_REVIEWED
    try:
        return OccupationStatus(str(entry.value))
    except ValueError:
        return OccupationStatus.NO_EVIDENCE_REVIEWED


def _notice(summary: FactTierSummary) -> NoticeStatus:
    entry = summary.confirmed.get(FACT_NOTICE_STATUS)
    if entry is None:
        return NoticeStatus.NO_EVIDENCE_REVIEWED
    try:
        return NoticeStatus(str(entry.value))
    except ValueError:
        return NoticeStatus.NO_EVIDENCE_REVIEWED


def to_matter_fact_snapshot(summary: FactTierSummary) -> MatterFactSnapshot:
    """Project the fact tier onto exactly what the gates read."""
    discharge_entry = summary.confirmed.get(FACT_DISCHARGE_EVIDENCE)
    discharge_sufficient = TriState.UNKNOWN
    if discharge_entry is not None:
        discharge_sufficient = (
            TriState.NO
            if str(discharge_entry.value).upper() in _INSUFFICIENT_DISCHARGE
            else TriState.YES
        )

    return MatterFactSnapshot(
        transferor_is_registered_owner=_tri(summary, FACT_TRANSFEROR_IS_OWNER),
        title_certificate_available=(
            TriState.YES if FACT_TITLE_CERTIFICATE in summary.confirmed else TriState.UNKNOWN
        ),
        transmission_completed=_tri(summary, FACT_TRANSMISSION_COMPLETED),
        life_interest_present=_tri(summary, FACT_LIFE_INTEREST),
        special_condition_present=_tri(summary, FACT_SPECIAL_CONDITION),
        coowners_present=_tri(summary, FACT_COOWNERS),
        creates_coownership=_tri(summary, FACT_CREATES_COOWNERSHIP),
        mortgage_status=_encumbrance(summary, FACT_MORTGAGE_STATUS),
        lease_status=_encumbrance(summary, FACT_LEASE_STATUS),
        occupation_status=_occupation(summary),
        notice_status=_notice(summary),
        active_court_proceeding=(
            TriState.YES if FACT_COURT_PROCEEDING in summary.confirmed else TriState.UNKNOWN
        ),
        # A conflicting title, parcel, extent, or owner fact is exactly the
        # identifier conflict §14.6 stops on.
        identifier_conflict_present=bool(summary.conflicted_fact_type_ids),
        unconfirmed_critical_fact_type_ids=summary.unconfirmed_critical_fact_type_ids,
        identified_mortgage_reference=FACT_MORTGAGE_REFERENCE in summary.confirmed,
        mortgagee_authority_confirmed=_tri(summary, FACT_MORTGAGEE_AUTHORITY),
        discharge_evidence_sufficient=discharge_sufficient,
        # The cancellation route is a legal characterisation, so it is only ever
        # true once the responsible lawyer has confirmed the subtype and the
        # Form 12 route; nothing extracted can establish it.
        cancellation_route_confirmed=TriState.UNKNOWN,
    )


class SqlMatterFactAdapter:
    """Implements ``matter.ports.MatterFactPort`` over the verification tier."""

    def __init__(
        self, session: AsyncSession, *, reader: ConfirmedFactReadPort | None = None
    ) -> None:
        self._reader: ConfirmedFactReadPort = reader or SqlConfirmedFactReader(session)

    async def snapshot(self, user_id: str, matter_id: str) -> MatterFactSnapshot:
        return to_matter_fact_snapshot(await self._reader.summarise(user_id, matter_id))
