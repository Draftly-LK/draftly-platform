"""Only the research owner supplies legal claims; the agent cannot compose its own."""

from src.modules.matter_agent.application.read_tools import _BaseTool
from src.modules.matter_agent.domain.models import AgentCitation
from src.modules.matter_agent.ports import ToolInvocation, ToolResult
from src.modules.research.contracts import MatterResearchPort
from src.modules.research.domain.models import SourceScope
from src.platform.errors import DomainRuleError


class ResearchLegalQuestionTool(_BaseTool):
    name = "research_legal_question"
    properties = {
        "question": {"type": "string", "maxLength": 10000},
        "sources": {"type": "string", "enum": ["statutes", "cases", "all"]},
    }
    required = ["question", "sources"]

    def __init__(self, research: MatterResearchPort) -> None:
        self._research = research

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        if invocation.context is None:
            raise DomainRuleError()
        answer = await self._research.answer(
            invocation.context,
            invocation.matter_id,
            question=invocation.arguments["question"],
            sources=SourceScope(invocation.arguments["sources"]),
            operation_id=invocation.job_id,
        )
        citations = tuple(
            AgentCitation(
                source_id=p.authority_id.upper(),
                source_type=p.kind.value,
                label=p.reference or p.title,
                # The retrieval flag establishes a source match, not lawyer review
                # or current/consolidated law. The approved release is unverified.
                verification_status="unverified",
                page=p.page,
                passage=p.text,
                corpus_version=p.corpus_version,
            )
            for p in answer.passages
        )
        numbers = {c.source_id: i + 1 for i, c in enumerate(citations)}
        text = "\n\n".join(
            claim.text + " " + " ".join(f"[{numbers[c]}]" for c in claim.citation_ids)
            for claim in answer.claims
        )
        return ToolResult(
            summary="Research returned supported claims."
            if text
            else "Legal research could not support an answer.",
            payload={
                "groundedText": text,
                "unavailableReason": answer.unavailable_reason,
                "degradedChannels": list(answer.degraded_channels),
            },
            resource_refs=tuple(c.source_id for c in citations),
            citations=citations,
        )
