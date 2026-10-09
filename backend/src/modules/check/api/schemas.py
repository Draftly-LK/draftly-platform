"""Wire contract for the check module.

Every result carries the versions it was pinned to and the source records it
rests on, because §7.1 makes those part of the result rather than metadata about
it: a lawyer must be able to see which facts, which rule pack, and which
authority produced a conclusion before relying on it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class _StrictCamel(_Camel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class RunChecksRequest(_StrictCamel):
    """Nothing legal is accepted from the client.

    The caller pins the reviewed association and may supply an office currency
    policy. Facts, rule definitions and matter routing are read server-side.
    """

    transaction_id: str
    subject_id: str | None = None
    association_version: int = Field(ge=1)
    search_currency_max_age_days: int | None = Field(default=None, ge=1, le=3650)


class IssueDecisionRequest(_StrictCamel):
    """One recorded disposition. The deciding lawyer is the authenticated actor."""

    state: str
    reason: str | None = None
    evidence_reference_ids: list[str] = Field(default_factory=list)
    assigned_to: str | None = None


class FactVersionPinRead(_Camel):
    fact_id: str
    version: int


class CheckResultRead(_Camel):
    transaction_id: str | None = None
    subject_id: str | None = None
    association_version: int | None = None
    id: str
    check_definition_id: str
    check_definition_version: str
    run_id: str
    outcome: str
    default_severity: str
    explanation_key: str
    #: The §7.2 "Safety rule/action" wording, as a translation key.
    safety_rule_key: str | None
    label_key: str | None
    comparison_key: str | None
    source_record_ids: list[str]
    #: The blocker kind a *failure* of this check carries, from the definition.
    #: An inconclusive result raises an evidence blocker instead; the issue is
    #: authoritative for what any one result actually produced.
    failure_blocker_kind: str | None
    input_fact_versions: list[FactVersionPinRead]
    evidence_reference_ids: list[str]
    requires_human_conclusion: bool
    #: True when the conclusion rests on a rule this repository cannot verify —
    #: today only the seven-working-day calendar (§16.4 item 5).
    provisional: bool
    created_at: str


class LegalIssueRead(_Camel):
    transaction_id: str | None = None
    subject_id: str | None = None
    association_version: int | None = None
    id: str
    matter_id: str
    check_id: str | None
    issue_type_id: str
    severity: str
    blocker_kind: str
    state: str
    summary_key: str
    source_record_ids: list[str]
    evidence_reference_ids: list[str]
    assigned_to: str | None
    resolution_decision_id: str | None
    resolution_reason: str | None
    #: The dispositions this issue's blocker kind can legitimately reach, so the
    #: UI never offers an acceptance the server will refuse (§7.3).
    permitted_states: list[str]
    created_at: str
    updated_at: str
    version: int


class IssueGatesRead(_Camel):
    blocks_draft_generation: bool
    blocks_approval: bool
    blocks_registration_ready_export: bool
    open_statutory_blocker_ids: list[str]
    open_blocking_issue_ids: list[str]
    stale_check_ids: list[str] = []


class PageInfo(_Camel):
    next_cursor: str | None
    has_more: bool
    limit: int


class CheckRunRead(_Camel):
    run_id: str
    results: list[CheckResultRead]
    raised_issues: list[LegalIssueRead]
    gates: IssueGatesRead


class CheckResultListRead(_Camel):
    items: list[CheckResultRead]
    page: PageInfo


class LegalIssueListRead(_Camel):
    items: list[LegalIssueRead]
    page: PageInfo
    gates: IssueGatesRead
