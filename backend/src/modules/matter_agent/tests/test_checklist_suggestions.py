"""Agent proposals stay separate from lawyer-recorded task completion."""

from types import SimpleNamespace

import pytest

from src.modules.auth.domain.models import Role
from src.modules.matter_agent.application import write_tools
from src.modules.matter_agent.application.validation import validate_arguments
from src.modules.matter_agent.ports import ToolInvocation
from src.platform.request_context import RequestContext


class Tasks:
    def __init__(self):
        self.proposals = {}

    async def create_suggestion(self, ctx, matter_id, **values):
        key = values["dedup_key"]
        self.proposals.setdefault(
            key,
            SimpleNamespace(
                id="suggestion-synthetic",
                state="pending-applicability",
                suggestion_status="pending",
                ctx=ctx,
                matter_id=matter_id,
                **values,
            ),
        )
        return self.proposals[key]


def call(title="Review synthetic boundary evidence"):
    return ToolInvocation(
        tool_name="suggest_checklist_item",
        actor_id="synthetic-actor",
        matter_id="synthetic-matter",
        job_id="synthetic-job",
        context=RequestContext("synthetic-actor", Role.REVIEWER),
        arguments={
            "title": title,
            "reason": "Compare the source pages.",
            "group": "evidence",
            "sourceFileId": "synthetic-source",
            "sourceVersion": 4,
        },
    )


async def test_agent_suggestion_is_pending_and_bound_to_its_exact_source():
    tool_type = getattr(write_tools, "SuggestChecklistItemTool", None)
    assert tool_type is not None, "the allowlisted operational proposal tool is missing"
    tasks = Tasks()
    result = await tool_type(tasks, session_id="synthetic-session").execute(call())
    proposal = next(iter(tasks.proposals.values()))
    assert proposal.state == "pending-applicability"
    assert proposal.suggestion_status == "pending"
    assert proposal.evidence[0].id == "synthetic-source"
    assert proposal.evidence[0].version == 4
    assert proposal.provenance["jobId"] == "synthetic-job"
    assert result.resource_refs == ("suggestion-synthetic",)
    assert "Review synthetic boundary evidence" not in result.summary


async def test_repeated_proposal_deduplicates_but_different_work_remains_distinct():
    tool_type = getattr(write_tools, "SuggestChecklistItemTool", None)
    assert tool_type is not None
    tasks = Tasks()
    tool = tool_type(tasks)
    await tool.execute(call())
    await tool.execute(call())
    assert len(tasks.proposals) == 1
    await tool.execute(call("Review synthetic extent evidence"))
    assert len(tasks.proposals) == 2


async def test_proposal_pins_only_current_interpretations_and_changes_identity_after_correction():
    class Documents:
        version = 2

        async def get_source_file(self, **kwargs):
            return SimpleNamespace(
                source_file=SimpleNamespace(matter_id="synthetic-matter"),
                detected_document_ids=("current", "historical"),
            )

        async def get_detected_document(self, **kwargs):
            document_id = kwargs["document_id"]
            return SimpleNamespace(
                document=SimpleNamespace(
                    id=document_id,
                    version=self.version,
                    interpretation_generation=self.version,
                    version_relationship="SUPERSEDED" if document_id == "historical" else None,
                    class_status="AI_ORGANIZED",
                )
            )

    documents = Documents()
    tasks = Tasks()
    tool = write_tools.SuggestChecklistItemTool(tasks, ingestion=documents)
    await tool.execute(call())
    proposal = next(iter(tasks.proposals.values()))
    assert len(proposal.evidence) == 2
    assert proposal.evidence[1].id == "current"
    documents.version += 1
    await tool.execute(call())
    assert len(tasks.proposals) == 2


def test_suggestion_declaration_rejects_legal_completion_fields():
    tool_type = getattr(write_tools, "SuggestChecklistItemTool", None)
    assert tool_type is not None
    declaration = tool_type(Tasks()).declaration()
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        validate_arguments(declaration, {**call().arguments, "complete": True})


async def test_processing_followthrough_publishes_only_successful_source_pins():
    from src.modules.matter_agent.application import task_suggestions

    publish = getattr(task_suggestions, "publish_processing_followthrough", None)
    assert publish is not None, "successful processing does not schedule checklist follow-through"
    events = []

    class Publisher:
        async def publish(self, name, **values):
            events.append((name, values))

    view = SimpleNamespace(
        run=SimpleNamespace(id="synthetic-run", succeeded=False),
        source_file=SimpleNamespace(id="synthetic-source", matter_id="synthetic-matter", version=4),
        documents=(
            SimpleNamespace(
                document=SimpleNamespace(
                    id="synthetic-document", version=2, interpretation_generation=3
                )
            ),
        ),
    )
    await publish(view, call().context, Publisher())
    assert not events
    view.run.succeeded = True
    await publish(view, call().context, Publisher())
    assert events[0][0] == "document.processing-completed"
    assert events[0][1]["data"] == {
        "sourceFileId": "synthetic-source",
        "sourceVersion": 4,
        "documentVersionId": "synthetic-source",
        "processingRunId": "synthetic-run",
        "docClass": "unknown",
        "derivatives": [],
        "documentReferences": [{"id": "synthetic-document", "version": 2, "generation": 3}],
    }
