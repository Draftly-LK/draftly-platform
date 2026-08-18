"""Synthetic placeholder template catalogue (notification-service.md §8).

These are **not** approved product or legal copy. Every entry is a synthetic
bilingual placeholder. Wherever prescribed statutory wording or legal advice
would belong, the copy carries LEGAL_WORDING_PLACEHOLDER: the responsible lawyer
supplies and approves that text, and no agent or developer may author it
(CLAUDE.md, notification-service.md §8 bullet 11).

Pure domain data: no FastAPI, SQLAlchemy, React Email, or provider imports.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from src.modules.notification.domain.models import NotificationLocale

LEGAL_WORDING_PLACEHOLDER = "[LEGAL WORDING PENDING: RESPONSIBLE LAWYER TO SUPPLY AND APPROVE]"
SINHALA_TRANSLATION_PLACEHOLDER = "[SI TRANSLATION PENDING HUMAN REVIEW]"


class TemplateApprovalState(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    RETIRED = "retired"


@dataclass(frozen=True)
class TemplateCopy:
    subject: str
    body: str


@dataclass(frozen=True)
class TemplateDefinition:
    """One template key at one version, with its variable contract."""

    key: str
    version: str
    approval_state: TemplateApprovalState
    required_variables: tuple[str, ...]
    copy: Mapping[str, TemplateCopy]
    carries_context: bool = True

    def copy_for(self, locale: NotificationLocale) -> TemplateCopy:
        """Return locale copy, falling back to English with an explicit marker."""
        entry = self.copy.get(locale.value)
        if entry is not None:
            return entry
        english = self.copy[NotificationLocale.EN.value]
        return TemplateCopy(
            subject=f"{SINHALA_TRANSLATION_PLACEHOLDER} {english.subject}",
            body=f"{SINHALA_TRANSLATION_PLACEHOLDER}\n{english.body}",
        )


def _bilingual(
    *,
    en_subject: str,
    en_body: str,
    si_subject: str,
    si_body: str,
) -> Mapping[str, TemplateCopy]:
    return {
        NotificationLocale.EN.value: TemplateCopy(subject=en_subject, body=en_body),
        NotificationLocale.SI.value: TemplateCopy(subject=si_subject, body=si_body),
    }


# Synthetic reference used by placeholder copy so no real matter data appears.
_ACTION_LINE_EN = f"Sign in to Draftly to review it. {LEGAL_WORDING_PLACEHOLDER}"
_ACTION_LINE_SI = f"සමාලෝචනය කිරීමට Draftly වෙත පිවිසෙන්න. {LEGAL_WORDING_PLACEHOLDER}"

_PRODUCT_VARIABLES = ("actionUrl",)
_DEADLINE_VARIABLES = ("actionUrl", "dueAt")

TEMPLATE_CATALOGUE: dict[str, TemplateDefinition] = {
    "obligation.reminder.due": TemplateDefinition(
        key="obligation.reminder.due",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_DEADLINE_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly deadline reminder (synthetic)",
            en_body=f"A synthetic obligation is due on {{dueAt}}. {_ACTION_LINE_EN}",
            si_subject="Draftly කාලසීමා මතක් කිරීම (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම බැඳීමක් {{dueAt}} දින නියමිතය. {_ACTION_LINE_SI}",
        ),
    ),
    "obligation.escalated": TemplateDefinition(
        key="obligation.escalated",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly deadline escalation (synthetic)",
            en_body=f"A synthetic obligation was escalated. {_ACTION_LINE_EN}",
            si_subject="Draftly කාලසීමා උත්සන්නය (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම බැඳීමක් උත්සන්න කර ඇත. {_ACTION_LINE_SI}",
        ),
    ),
    "obligation.deadline_changed": TemplateDefinition(
        key="obligation.deadline_changed",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly deadline updated (synthetic)",
            en_body=f"A synthetic obligation deadline was recorded. {_ACTION_LINE_EN}",
            si_subject="Draftly කාලසීමාව යාවත්කාලීන විය (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම බැඳීමක කාලසීමාව සටහන් විය. {_ACTION_LINE_SI}",
        ),
    ),
    "matter.assignment_changed": TemplateDefinition(
        key="matter.assignment_changed",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly assignment update (synthetic)",
            en_body=f"A synthetic matter assignment changed. {_ACTION_LINE_EN}",
            si_subject="Draftly පැවරුම් යාවත්කාලීනය (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම කාරණයක පැවරුම වෙනස් විය. {_ACTION_LINE_SI}",
        ),
    ),
    "review.requested": TemplateDefinition(
        key="review.requested",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly review requested (synthetic)",
            en_body=f"A synthetic item is waiting for review. {_ACTION_LINE_EN}",
            si_subject="Draftly සමාලෝචනය ඉල්ලා ඇත (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම අයිතමයක් සමාලෝචනය සඳහා රැඳී සිටී. {_ACTION_LINE_SI}",
        ),
    ),
    "workflow.setup_failed": TemplateDefinition(
        key="workflow.setup_failed",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly workflow setup failed (synthetic)",
            en_body=f"A synthetic workflow could not be set up. {_ACTION_LINE_EN}",
            si_subject="Draftly කාර්ය ප්‍රවාහ සැකසුම අසාර්ථක විය (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම කාර්ය ප්‍රවාහයක් සැකසීමට නොහැකි විය. {_ACTION_LINE_SI}",
        ),
    ),
    "workflow.signing_scheduled": TemplateDefinition(
        key="workflow.signing_scheduled",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly signing appointment (synthetic)",
            en_body=f"A synthetic signing appointment was scheduled. {_ACTION_LINE_EN}",
            si_subject="Draftly අත්සන් කිරීමේ හමුව (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම අත්සන් කිරීමේ හමුවක් සැලසුම් විය. {_ACTION_LINE_SI}",
        ),
    ),
    "document.processing_failed": TemplateDefinition(
        key="document.processing_failed",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly document processing failed (synthetic)",
            en_body=f"A synthetic document could not be processed. {_ACTION_LINE_EN}",
            si_subject="Draftly ලේඛන සැකසීම අසාර්ථක විය (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම ලේඛනයක් සැකසීමට නොහැකි විය. {_ACTION_LINE_SI}",
        ),
    ),
    "document.replacement_ready": TemplateDefinition(
        key="document.replacement_ready",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly replacement ready (synthetic)",
            en_body=f"A synthetic replacement version is ready for review. {_ACTION_LINE_EN}",
            si_subject="Draftly ප්‍රතිස්ථාපනය සූදානම් (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම ප්‍රතිස්ථාපන අනුවාදයක් සමාලෝචනයට සූදානම්. {_ACTION_LINE_SI}",
        ),
    ),
    "instrument.collection_ready": TemplateDefinition(
        key="instrument.collection_ready",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly collection ready (synthetic)",
            en_body=f"A synthetic registered instrument is ready for collection. {_ACTION_LINE_EN}",
            si_subject="Draftly එකතු කිරීමට සූදානම් (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම ලියවිල්ලක් එකතු කිරීමට සූදානම්. {_ACTION_LINE_SI}",
        ),
    ),
    "draft.approved": TemplateDefinition(
        key="draft.approved",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly approval recorded (synthetic)",
            en_body=f"A synthetic approval was recorded. {_ACTION_LINE_EN}",
            si_subject="Draftly අනුමැතිය සටහන් විය (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම අනුමැතියක් සටහන් විය. {_ACTION_LINE_SI}",
        ),
    ),
    "draft.approval_invalidated": TemplateDefinition(
        key="draft.approval_invalidated",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly approval invalidated (synthetic)",
            en_body=f"A synthetic approval was invalidated. {_ACTION_LINE_EN}",
            si_subject="Draftly අනුමැතිය අවලංගු විය (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම අනුමැතියක් අවලංගු විය. {_ACTION_LINE_SI}",
        ),
    ),
    "export.ready": TemplateDefinition(
        key="export.ready",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly export ready (synthetic)",
            en_body=f"A synthetic export finished rendering. {_ACTION_LINE_EN}",
            si_subject="Draftly නිර්යාතය සූදානම් (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම නිර්යාතයක් සම්පූර්ණ විය. {_ACTION_LINE_SI}",
        ),
    ),
    "export.failed": TemplateDefinition(
        key="export.failed",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly export failed (synthetic)",
            en_body=f"A synthetic export could not be produced. {_ACTION_LINE_EN}",
            si_subject="Draftly නිර්යාතය අසාර්ථක විය (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම නිර්යාතයක් සෑදීමට නොහැකි විය. {_ACTION_LINE_SI}",
        ),
    ),
    "user.invited": TemplateDefinition(
        key="user.invited",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly invitation (synthetic)",
            en_body=f"You have a synthetic Draftly invitation. {_ACTION_LINE_EN}",
            si_subject="Draftly ආරාධනය (කෘත්‍රිම)",
            si_body=f"ඔබට කෘත්‍රිම Draftly ආරාධනයක් ඇත. {_ACTION_LINE_SI}",
        ),
    ),
    "account.status_changed": TemplateDefinition(
        key="account.status_changed",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly account update (synthetic)",
            en_body=f"A synthetic account status changed. {_ACTION_LINE_EN}",
            si_subject="Draftly ගිණුම් යාවත්කාලීනය (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම ගිණුම් තත්ත්වයක් වෙනස් විය. {_ACTION_LINE_SI}",
        ),
    ),
    "billing.notice": TemplateDefinition(
        key="billing.notice",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=_PRODUCT_VARIABLES,
        copy=_bilingual(
            en_subject="Draftly billing notice (synthetic)",
            en_body=f"A synthetic billing notice needs your attention. {_ACTION_LINE_EN}",
            si_subject="Draftly බිල්පත් දැනුම්දීම (කෘත්‍රිම)",
            si_body=f"කෘත්‍රිම බිල්පත් දැනුම්දීමකට ඔබේ අවධානය අවශ්‍යය. {_ACTION_LINE_SI}",
        ),
    ),
    # Restricted compliance: neutral action-required only. No context variables
    # are accepted, so no matter, party, or list-match detail can reach the
    # subject, body, preview, or provider (notification-service.md §8.2).
    "restricted.action_required": TemplateDefinition(
        key="restricted.action_required",
        version="1.0.0-synthetic",
        approval_state=TemplateApprovalState.APPROVED,
        required_variables=(),
        carries_context=False,
        copy=_bilingual(
            en_subject="Draftly action required",
            en_body="An item in Draftly needs your attention. Sign in to continue.",
            si_subject="Draftly ක්‍රියාමාර්ගය අවශ්‍යය",
            si_body="Draftly තුළ අයිතමයකට ඔබේ අවධානය අවශ්‍යය. පිවිසෙන්න.",
        ),
    ),
}


def get_template(template_key: str) -> TemplateDefinition | None:
    return TEMPLATE_CATALOGUE.get(template_key)


def render(
    template: TemplateDefinition,
    *,
    locale: NotificationLocale,
    variables: Mapping[str, str],
) -> TemplateCopy:
    """Render subject and body, rejecting missing or unknown variables."""
    missing = [name for name in template.required_variables if not variables.get(name)]
    if missing:
        raise MissingTemplateVariablesError(template.key, tuple(missing))
    unknown = [name for name in variables if name not in template.required_variables]
    if unknown:
        raise UnknownTemplateVariablesError(template.key, tuple(sorted(unknown)))

    entry = template.copy_for(locale)
    allowed = {name: variables[name] for name in template.required_variables}
    return TemplateCopy(
        subject=entry.subject.format(**allowed),
        body=entry.body.format(**allowed),
    )


class TemplateVariableError(ValueError):
    """Base for template variable contract violations."""

    def __init__(self, template_key: str, variables: tuple[str, ...]) -> None:
        self.template_key = template_key
        self.variables = variables
        super().__init__(f"{template_key}: {', '.join(variables)}")


class MissingTemplateVariablesError(TemplateVariableError):
    """A required variable was absent — dead-letter, never send a partial email."""


class UnknownTemplateVariablesError(TemplateVariableError):
    """A variable outside the template contract was supplied."""


__all__ = [
    "LEGAL_WORDING_PLACEHOLDER",
    "SINHALA_TRANSLATION_PLACEHOLDER",
    "TEMPLATE_CATALOGUE",
    "MissingTemplateVariablesError",
    "TemplateApprovalState",
    "TemplateCopy",
    "TemplateDefinition",
    "TemplateVariableError",
    "UnknownTemplateVariablesError",
    "get_template",
    "render",
]
