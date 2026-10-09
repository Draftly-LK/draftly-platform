"""Immutable legal result context and lossless JSON codecs; never claim evidence."""

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Literal

from src.modules.corpus_governance.contracts import AuthorityMetadata, AuthorityRelationship
from src.modules.research.contracts import LegalDateContext


@dataclass(frozen=True)
class AgentLegalContext:
    kind: Literal["selection", "result"] = "result"
    transaction_id: str | None = None
    association_version: int | None = None
    date_context: LegalDateContext | None = None
    authorities: tuple[AuthorityMetadata, ...] = ()
    coverage_gaps: tuple[str, ...] = ()
    source_release_version: str | None = None
    unavailable_reason: str | None = None
    visibility: Literal["available", "current-policy-unavailable"] = "available"


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value is not None else None


def authority_payload(value: AuthorityMetadata) -> dict[str, Any]:
    return {
        **asdict(value),
        "publication_date": value.publication_date.isoformat()
        if value.publication_date is not None
        else None,
        "effective_from": value.effective_from.isoformat()
        if value.effective_from is not None
        else None,
        "effective_to": value.effective_to.isoformat() if value.effective_to is not None else None,
        "relationships": [asdict(r) for r in value.relationships],
    }


def authority_from_payload(value: dict[str, Any]) -> AuthorityMetadata:
    return AuthorityMetadata(
        **{
            **value,
            "publication_date": _date(value["publication_date"]),
            "effective_from": _date(value["effective_from"]),
            "effective_to": _date(value["effective_to"]),
            "relationships": tuple(AuthorityRelationship(**r) for r in value["relationships"]),
        }
    )


def legal_context_payload(value: AgentLegalContext) -> dict[str, Any]:
    context = value.date_context
    return {
        **asdict(value),
        "date_context": {
            **asdict(context),
            "current_date": context.current_date.isoformat(),
            "transaction_date": context.transaction_date.isoformat()
            if context.transaction_date is not None
            else None,
        }
        if context is not None
        else None,
        "authorities": [authority_payload(a) for a in value.authorities],
        "coverage_gaps": list(value.coverage_gaps),
    }


def legal_context_from_payload(value: dict[str, Any]) -> AgentLegalContext:
    context = value.get("date_context")
    return AgentLegalContext(
        **{
            **value,
            "date_context": LegalDateContext(
                **{
                    **context,
                    "current_date": date.fromisoformat(context["current_date"]),
                    "transaction_date": _date(context["transaction_date"]),
                }
            )
            if context is not None
            else None,
            "authorities": tuple(authority_from_payload(a) for a in value.get("authorities", [])),
            "coverage_gaps": tuple(value.get("coverage_gaps", [])),
        }
    )
