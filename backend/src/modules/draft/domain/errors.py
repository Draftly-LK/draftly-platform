"""Drafting domain errors.

Each refusal has its own code because each one tells the lawyer a different
thing to do: confirm the subtype, confirm the fact, resolve the issue, or open a
new form version. A generic 422 would collapse four different next actions into
one message.
"""

from __future__ import annotations

from src.platform.errors import ConflictError, DomainRuleError, NotFoundError


class GeneratedFormNotFoundError(NotFoundError):
    code = "generated_form_not_found"
    message = "The requested generated form was not found."


class GeneratedFormFieldNotFoundError(NotFoundError):
    code = "generated_form_field_not_found"
    message = "The requested form field is not part of this form."


class SubtypeNotConfirmedError(DomainRuleError):
    """Drafting starts from a confirmed exact instrument, never a guess (§9.1).

    A provisional subtype is a routing hypothesis. Generating a registration
    oriented instrument from one would put the product's guess on the document
    the lawyer signs.
    """

    code = "rta_form_subtype_not_confirmed"
    message = (
        "The exact instrument for this matter has not been confirmed by the responsible "
        "lawyer. A registration-oriented draft cannot be generated from a provisional "
        "classification."
    )


class TemplateNotAvailableForSubtypeError(DomainRuleError):
    """§9.1 — the template is derived from the subtype, not from a request body."""

    code = "rta_form_template_not_available"
    message = (
        "No prescribed form template is registered for this matter's confirmed instrument, "
        "or the requested template is not one of the templates that instrument selects."
    )


class FormGenerationBlockedError(DomainRuleError):
    """§7.3 — a BLOCKING issue stops generation; a HIGH_RISK one does not."""

    code = "rta_form_generation_blocked"
    message = (
        "An open blocking issue on this matter stops form generation. Resolve the issue, "
        "provide the missing evidence, or move the matter to the manual workflow."
    )


class CriticalFieldRequiresConfirmedFactError(DomainRuleError):
    """A critical field is never typed into the form (§9.3, §6.4).

    Its own code because this is the rule a busy user will most want to route
    around: the value has to become a lawyer-confirmed *fact* in the verification
    queue, where it keeps its evidence, before any form can carry it.
    """

    code = "rta_form_critical_field_requires_confirmed_fact"
    message = (
        "A critical form field can only be populated from a lawyer-confirmed canonical "
        "fact with page-level evidence. Confirm the fact against its source, then "
        "regenerate or re-resolve the field."
    )


class CriticalFieldEvidenceMissingError(DomainRuleError):
    """A populated critical field with no evidence chain is a defect, not a draft."""

    code = "rta_form_critical_field_evidence_missing"
    message = (
        "A populated critical form field must carry its canonical fact id, the exact fact "
        "version, and at least one page-level evidence reference."
    )


class PreCertificationNotPermittedError(DomainRuleError):
    """§9.3 — signature, witness appearance, inspection, and attestation.

    None of them may be pre-filled or pre-confirmed on a draft. They are human
    execution events, recorded after they happen.
    """

    code = "rta_form_pre_certification_not_permitted"
    message = (
        "Signature, witness appearance, original inspection, and attestation particulars "
        "are never pre-certified on a draft. They are recorded from the execution event."
    )


class LawyerAuthoredTextNotPermittedError(DomainRuleError):
    """§9.4 — free drafting text only where the template permits it."""

    code = "rta_form_lawyer_authored_text_not_permitted"
    message = "This template field does not permit lawyer-authored text."


class ApprovedFormImmutableError(DomainRuleError):
    """§9.5, §10.7 — an approved snapshot is amended by a new form version."""

    code = "rta_form_approved_snapshot_immutable"
    message = (
        "This form has been approved and its snapshot is immutable. Amending it requires "
        "a new form version and a fresh approval."
    )


class FieldDecisionReasonRequiredError(DomainRuleError):
    code = "rta_form_field_decision_reason_required"
    message = "Correcting or clearing a form field requires a recorded reason."


class FieldNotPopulatedError(DomainRuleError):
    """There is nothing to confirm on a field that renders an unresolved token."""

    code = "rta_form_field_not_populated"
    message = (
        "This field has no value to confirm. Resolve the underlying fact first; a "
        "confirmation of an unresolved token would record a decision about nothing."
    )


class FieldValueRequiredError(DomainRuleError):
    code = "rta_form_field_value_required"
    message = "Correcting a form field requires the corrected value."


class GeneratedFormStaleError(ConflictError):
    code = "generated_form_version_stale"
    message = "The generated form changed since your last read."
