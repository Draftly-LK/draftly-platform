"""Current-policy presentation projection. Stored rows and hashes stay untouched."""

import asyncio
from dataclasses import replace

from src.modules.matter_agent.domain.legal_context import AgentLegalContext
from src.modules.matter_agent.domain.models import AgentMessage, MessageRole
from src.modules.research.contracts import LegalSourceAvailabilityPort

LEGAL_KINDS = frozenset({"statute", "amendment", "gazette", "case"})
WITHHELD_TEXT = "The saved legal answer is unavailable under the current source policy. Its source references and date context are retained."


async def project_legal_history(
    messages: tuple[AgentMessage, ...], availability: LegalSourceAvailabilityPort | None
) -> tuple[AgentMessage, ...]:
    groups: dict[str, set[str]] = {}
    for message in messages:
        if message.role is not MessageRole.ASSISTANT:
            continue
        for citation in message.citations:
            if citation.source_type in LEGAL_KINDS:
                source_id = (
                    citation.authority_metadata.source_id
                    if citation.authority_metadata is not None
                    else citation.source_id
                )
                groups.setdefault(citation.corpus_version or "", set()).add(source_id)
    allowed: dict[str, bool] = {}
    semaphore = asyncio.Semaphore(4)

    async def check(version: str, source_ids: set[str]) -> None:
        if not version or availability is None or len(source_ids) > 100:
            return
        try:
            async with semaphore:
                allowed[version] = await availability.passages_available(
                    tuple(sorted(source_ids)), corpus_version=version
                )
        except Exception:
            allowed[version] = False

    try:
        async with asyncio.timeout(4):
            await asyncio.gather(
                *(check(version, sources) for version, sources in list(groups.items())[:8])
            )
    except TimeoutError:
        pass
    projected = []
    for message in messages:
        legal = (
            [c for c in message.citations if c.source_type in LEGAL_KINDS]
            if message.role is MessageRole.ASSISTANT
            else []
        )
        if legal and any(not allowed.get(c.corpus_version or "", False) for c in legal):
            context = replace(
                message.legal_context or AgentLegalContext(),
                visibility="current-policy-unavailable",
            )
            projected.append(
                replace(
                    message,
                    content=WITHHELD_TEXT,
                    citations=tuple(
                        replace(c, passage=None) if c.source_type in LEGAL_KINDS else c
                        for c in message.citations
                    ),
                    legal_context=context,
                )
            )
        else:
            projected.append(message)
    return tuple(projected)
