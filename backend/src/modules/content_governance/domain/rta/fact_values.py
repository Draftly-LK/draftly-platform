"""Enumerated values for the RTA facts whose value space is legally meaningful.

These are separated from `facts.py` (which declares *what* can be known) because
the distinctions here carry the safety rules. In particular none of them has a
plain "no" member: the absence of a registered interest is only knowable from a
current search plus a lawyer's conclusion, never from the absence of an uploaded
document (§6.4, §7.2).
"""

from __future__ import annotations

from enum import Enum


class EncumbranceStatus(str, Enum):
    """Status of a registered interest such as a mortgage or a lease.

    ``NOT_FOUND_IN_CURRENT_SEARCH`` is deliberately not called "none": it
    records what a dated search showed, not a guarantee that no later entry
    exists (§5.3). ``NO_EVIDENCE_REVIEWED`` is the honest default before any
    search is uploaded — it is not a negative answer.
    """

    NO_EVIDENCE_REVIEWED = "NO_EVIDENCE_REVIEWED"
    NOT_FOUND_IN_CURRENT_SEARCH = "NOT_FOUND_IN_CURRENT_SEARCH"
    APPARENTLY_UNCANCELLED = "APPARENTLY_UNCANCELLED"
    REGISTERED_AND_CURRENT = "REGISTERED_AND_CURRENT"
    DISCHARGE_CLAIMED_NOT_REGISTERED = "DISCHARGE_CLAIMED_NOT_REGISTERED"
    CANCELLATION_REGISTERED = "CANCELLATION_REGISTERED"

    @property
    def blocks_transfer_approval(self) -> bool:
        """§7.2 CHK_MORTGAGE_STATUS: a paid loan is not a cancelled interest.

        A settlement letter moves the status to
        ``DISCHARGE_CLAIMED_NOT_REGISTERED``; it does not clear the gate.
        """
        return self in {
            EncumbranceStatus.NO_EVIDENCE_REVIEWED,
            EncumbranceStatus.APPARENTLY_UNCANCELLED,
            EncumbranceStatus.REGISTERED_AND_CURRENT,
            EncumbranceStatus.DISCHARGE_CLAIMED_NOT_REGISTERED,
        }


class OccupationStatus(str, Enum):
    """Who is in possession (§4.3 Q11). Silence in uploaded papers is not proof."""

    NO_EVIDENCE_REVIEWED = "NO_EVIDENCE_REVIEWED"
    VACANT_CONFIRMED_BY_LAWYER = "VACANT_CONFIRMED_BY_LAWYER"
    OWNER_OCCUPIED = "OWNER_OCCUPIED"
    THIRD_PARTY_OCCUPATION = "THIRD_PARTY_OCCUPATION"
    UNDER_REGISTERED_LEASE = "UNDER_REGISTERED_LEASE"


class NoticeStatus(str, Enum):
    """Caveat, seizure, priority notice, injunction, or lis pendens (§4.3 Q14)."""

    NO_EVIDENCE_REVIEWED = "NO_EVIDENCE_REVIEWED"
    NOT_FOUND_IN_CURRENT_SEARCH = "NOT_FOUND_IN_CURRENT_SEARCH"
    PRESENT_UNRESOLVED = "PRESENT_UNRESOLVED"
    PRESENT_RESOLVED = "PRESENT_RESOLVED"


class TitleClass(str, Enum):
    """RTA s. 14 outcomes.

    First Class under s. 14(a) and Second Class under s. 14(b); a handout that
    labels Second Class as s. 14(a) is wrong (§1.2). ``DIVIDED_PORTION`` is
    s. 14(c) and ``CO_OWNERSHIP`` is s. 14(d).
    """

    UNKNOWN = "UNKNOWN"
    FIRST_CLASS = "FIRST_CLASS"
    SECOND_CLASS = "SECOND_CLASS"
    DIVIDED_PORTION = "DIVIDED_PORTION"
    CO_OWNERSHIP = "CO_OWNERSHIP"


class ProbatePath(str, Enum):
    """§4.3 Q09 — which transmission route applies."""

    UNKNOWN = "UNKNOWN"
    TESTATE = "TESTATE"
    INTESTATE = "INTESTATE"
    COURT_ORDER_OR_CERTIFICATE = "COURT_ORDER_OR_CERTIFICATE"


class DischargeEvidenceKind(str, Enum):
    """What is offered as proof that a mortgage is discharged (§15.8).

    A payment receipt alone is insufficient; which of the others suffices is a
    lawyer-validation question (§16.1 item 8), so nothing here is treated as
    automatically conclusive.
    """

    NONE = "NONE"
    PAYMENT_RECEIPT_ONLY = "PAYMENT_RECEIPT_ONLY"
    SETTLEMENT_LETTER = "SETTLEMENT_LETTER"
    ORIGINAL_CANCELLED_BOND = "ORIGINAL_CANCELLED_BOND"
    DEED_OF_RELEASE = "DEED_OF_RELEASE"
    REGISTERED_CANCELLATION = "REGISTERED_CANCELLATION"
