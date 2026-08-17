"""Approval, export, and registration domain errors.

Each refusal carries its own code because each one names a different next act:
confirm the fact, resolve the issue, record the presentation, or open a new form
version. Collapsing them into one 422 would tell a lawyer that something is
wrong without telling them what to do about it.
"""

from __future__ import annotations

from src.platform.errors import (
    CapabilityDeniedError,
    ConflictError,
    DomainRuleError,
    NotFoundError,
)


class ApprovalTargetNotFoundError(NotFoundError):
    """Absent, or belonging to someone else — indistinguishable by design."""

    code = "rta_approval_target_not_found"
    message = "The generated form named in this request was not found."


class ApproverNotResponsibleLawyerError(CapabilityDeniedError):
    """§12.5 — approval belongs to the lawyer responsible for *this* matter.

    Separate from the generic capability denial because the remedy is different:
    the caller does not need a wider role, they need the file reassigned. No
    service account and no automated path can ever satisfy this.
    """

    code = "rta_approval_not_responsible_lawyer"
    message = (
        "Only the lawyer recorded as responsible for this matter may approve its "
        "instruments. Approving is a personal professional act and cannot be delegated "
        "to another account or to an automated path."
    )


class ApprovalTargetNotSupportedError(DomainRuleError):
    """Only a generated form is approvable here (§12.2 ``ApprovalTargetType``)."""

    code = "rta_approval_target_not_supported"
    message = "This module approves generated forms; other approval targets are not implemented."


class ApprovalPreflightUncleanError(DomainRuleError):
    """§9.4, §14.6 — an unclean preflight is a stop condition, not a warning."""

    code = "rta_approval_preflight_unclean"
    message = (
        "This form cannot be approved while its preflight is unclean. Resolve every "
        "required field, confirm every critical fact, and close every open blocker first."
    )


class ApprovalStatutoryBlockerError(DomainRuleError):
    """§7.3, §10.6 — a statutory blocker is not overridable by any role.

    Its own code so the interface can say "this cannot be waived" rather than
    "ask someone with a wider role", which would be false.
    """

    code = "rta_approval_statutory_blocker_open"
    message = (
        "An open statutory blocker stops approval. No role inside Draftly can override "
        "it; the underlying legal requirement has to be satisfied."
    )


class ApprovalWarningsNotDisposedError(DomainRuleError):
    """§9.6 — the approval records the warnings the lawyer accepted.

    A disposition list that does not match the warnings the server computed is
    not a record of what was accepted, so it is refused rather than stored.
    """

    code = "rta_approval_warnings_not_disposed"
    message = (
        "Every outstanding warning must be listed in the approval's dispositions, and "
        "no disposition may name a warning this form does not have."
    )


class ApprovalFormStaleError(DomainRuleError):
    """§9.5, §10.7 — a stale form is amended by a new version, not approved."""

    code = "rta_approval_form_stale"
    message = (
        "This form is stale: an input it was drafted from has moved. Generate a new form "
        "version against the current record and approve that."
    )


class ApprovalFormNotReviewableError(DomainRuleError):
    """§10.7 — approval follows field review, not generation."""

    code = "rta_approval_form_not_reviewable"
    message = (
        "This form is not in a state that can be approved. Only a form whose fields are "
        "resolved and whose review is complete may be approved."
    )


class ApprovalDeclarationUnknownError(DomainRuleError):
    """The declaration is a governed record, not free text supplied per request."""

    code = "rta_approval_declaration_unknown"
    message = "The requested approval declaration version is not registered."


class ApprovalSupersededError(DomainRuleError):
    """§17 — a correction after approval prevents reuse of the old approval."""

    code = "rta_approval_superseded"
    message = (
        "The approved snapshot no longer matches the matter's record: a fact, template, "
        "or field bound into it has changed since approval. The form has been marked "
        "stale and the earlier approval cannot be reused."
    )


class ApprovalRevokedError(DomainRuleError):
    code = "rta_approval_revoked"
    message = "This approval was superseded by a later one and cannot be used."


class ApprovalAlreadyCurrentError(ConflictError):
    """Approving the same unchanged snapshot twice is a duplicate, not an update."""

    code = "rta_approval_already_current"
    message = "This exact form snapshot already carries a current approval."


class ExportRequiresApprovalError(DomainRuleError):
    """§9.6 — an approved export is a projection of an approval, not of a draft."""

    code = "rta_form_export_requires_approval"
    message = (
        "An approved export requires a current approval of this exact snapshot. Take a "
        "watermarked working-draft export instead, or approve the form first."
    )


class RegistrationEvidenceRequiredError(DomainRuleError):
    """§10.1, §17 — a registry event is recorded from evidence, never inferred."""

    code = "rta_registration_event_evidence_required"
    message = (
        "Attestation, presentation, and registration are recorded from official evidence. "
        "At least one evidence reference is required, and time never advances them."
    )


class RegistrationEventDateInFutureError(DomainRuleError):
    code = "rta_registration_event_date_in_future"
    message = "A registration event is recorded after it happens; its date cannot be in the future."


class RegistrationEventFormRequiredError(DomainRuleError):
    """Attestation and registration are acts performed on one identified instrument."""

    code = "rta_registration_event_form_required"
    message = (
        "This event records an act performed on a specific instrument, so the generated "
        "form it was performed on must be named."
    )


class RegistrationDayBookReferenceRequiredError(DomainRuleError):
    code = "rta_registration_day_book_reference_required"
    message = "A day book entry is recorded with the registry's own day book reference."


class RegistrationResultNoteRequiredError(DomainRuleError):
    """A refusal or return without its recorded reason is not a record of one."""

    code = "rta_registration_result_note_required"
    message = "A refusal or return is recorded with the reason the registry gave."


class RegistrationOutOfOrderError(DomainRuleError):
    """§10.1 — ``EXPORTED -> SUBMITTED -> REGISTERED``, each on human evidence."""

    code = "rta_registration_event_out_of_order"
    message = (
        "Registration follows presentation. Record the presentation or day book entry, "
        "with its evidence, before recording the registry's result."
    )


class RegistrationAlreadyRecordedError(ConflictError):
    code = "rta_registration_already_recorded"
    message = "A registration result is already recorded for this instrument."
