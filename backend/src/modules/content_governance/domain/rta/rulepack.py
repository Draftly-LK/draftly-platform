"""Assembly and integrity of the RTA rule pack.

The pack is a set of independently authored catalogues that reference each
other by stable id: a subtype names checklist modules, a module names
requirements, a requirement names document classes and source records, a check
names fact types, a template names subtypes. Nothing enforces those references
at import time, so `validate_rule_pack` does — and a test runs it, which is why
a dangling id fails CI rather than a lawyer's screen.

`RULE_PACK_VERSION` is the single value pinned into every checklist snapshot,
check run, and preflight. A rule change therefore produces a new snapshot
rather than retroactively altering an old one (§13.2.7).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.modules.content_governance.domain.enums import BlockerKind
from src.modules.content_governance.domain.rta import checklist as checklist_mod
from src.modules.content_governance.domain.rta import checks as checks_mod
from src.modules.content_governance.domain.rta import documents as documents_mod
from src.modules.content_governance.domain.rta import forms as forms_mod
from src.modules.content_governance.domain.rta import questions as questions_mod
from src.modules.content_governance.domain.rta import taxonomy as taxonomy_mod
from src.modules.content_governance.domain.rta.compiler import COMPILER_VERSION
from src.modules.content_governance.domain.rta.eligibility import ELIGIBILITY_VERSION
from src.modules.content_governance.domain.rta.facts import FACT_TYPES
from src.modules.content_governance.domain.sources import get_source_record

RULE_PACK_VERSION = "1.0.0"

#: Blocker kinds §7.3 lets an authorised actor override with a recorded reason.
_OVERRIDABLE_KINDS = frozenset({BlockerKind.OFFICE_POLICY, BlockerKind.PROFESSIONAL_JUDGMENT})


@dataclass(frozen=True)
class RulePackVersions:
    """Every version a snapshot pins. Stored, not recomputed, on each snapshot."""

    rule_pack: str = RULE_PACK_VERSION
    taxonomy: str = taxonomy_mod.TAXONOMY_VERSION
    questions: str = questions_mod.QUESTIONS_VERSION
    checklist: str = checklist_mod.CHECKLIST_VERSION
    checks: str = checks_mod.CHECKS_VERSION
    forms: str = forms_mod.FORMS_VERSION
    document_classes: str = documents_mod.DOCUMENT_CLASSES_VERSION
    compiler: str = COMPILER_VERSION
    eligibility: str = ELIGIBILITY_VERSION

    def as_dict(self) -> dict[str, str]:
        return {
            "rulePack": self.rule_pack,
            "taxonomy": self.taxonomy,
            "questions": self.questions,
            "checklist": self.checklist,
            "checks": self.checks,
            "forms": self.forms,
            "documentClasses": self.document_classes,
            "compiler": self.compiler,
            "eligibility": self.eligibility,
        }


CURRENT_VERSIONS = RulePackVersions()


class RulePackIntegrityError(Exception):
    """A reference in the rule pack does not resolve. Fails the build."""


def _duplicates(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in ids:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return sorted(dupes)


def validate_rule_pack() -> None:
    """Raise ``RulePackIntegrityError`` listing every broken reference.

    Collects all problems before raising: fixing one dangling id at a time
    through a build is a poor use of anyone's afternoon.
    """
    problems: list[str] = []

    subtype_ids = [s.id for s in taxonomy_mod.ALL_SUBTYPES]
    module_ids = [m.id for m in checklist_mod.CHECKLIST_MODULES]
    requirement_ids = [r.id for r in checklist_mod.REQUIREMENTS]
    template_ids = [t.id for t in forms_mod.FORM_TEMPLATES]
    check_ids = [c.id for c in checks_mod.CHECK_DEFINITIONS]
    question_ids = [q.id for q in questions_mod.ALL_QUESTIONS]
    document_class_ids = [d.id for d in documents_mod.DOCUMENT_CLASSES]
    fact_type_ids = {f.id for f in FACT_TYPES}
    conditional_ids = {m.id for m in taxonomy_mod.CONDITIONAL_MODULES}

    for name, ids in (
        ("subtype", subtype_ids),
        ("checklist module", module_ids),
        ("requirement", requirement_ids),
        ("form template", template_ids),
        ("check", check_ids),
        ("question", question_ids),
        ("document class", document_class_ids),
        ("fact type", sorted(fact_type_ids)),
    ):
        for duplicate in _duplicates(list(ids)):
            problems.append(f"duplicate {name} id: {duplicate}")

    # Exactly 22 prescribed Gazette instruments — no more, no fewer (§3.3).
    if len(taxonomy_mod.PRESCRIBED_INSTRUMENTS) != 22:
        problems.append(
            f"expected 22 prescribed instruments, found {len(taxonomy_mod.PRESCRIBED_INSTRUMENTS)}"
        )

    module_id_set = set(module_ids)
    requirement_id_set = set(requirement_ids)
    template_id_set = set(template_ids)
    subtype_id_set = set(subtype_ids)
    document_class_id_set = set(document_class_ids)

    for subtype in taxonomy_mod.ALL_SUBTYPES:
        for module_id in subtype.default_module_definition_ids:
            if module_id not in module_id_set:
                problems.append(f"subtype {subtype.id} -> unknown checklist module {module_id}")
        for template_id in (subtype.form_template_id, *subtype.companion_template_ids):
            if template_id is not None and template_id not in template_id_set:
                problems.append(f"subtype {subtype.id} -> unknown form template {template_id}")
        for citation in subtype.sources:
            if get_source_record(citation.source_record_id) is None:
                problems.append(
                    f"subtype {subtype.id} -> unknown source {citation.source_record_id}"
                )

    for conditional in taxonomy_mod.CONDITIONAL_MODULES:
        for module_id in conditional.checklist_module_ids:
            if module_id not in module_id_set:
                problems.append(
                    f"conditional module {conditional.id} -> unknown checklist module {module_id}"
                )

    for module in checklist_mod.CHECKLIST_MODULES:
        for requirement_id in module.requirement_ids:
            if requirement_id not in requirement_id_set:
                problems.append(f"module {module.id} -> unknown requirement {requirement_id}")

    for requirement in checklist_mod.REQUIREMENTS:
        if requirement.module_id not in module_id_set:
            problems.append(
                f"requirement {requirement.id} -> unknown module {requirement.module_id}"
            )
        if not requirement.sources:
            problems.append(f"requirement {requirement.id} has no source citation")
        for citation in requirement.sources:
            if get_source_record(citation.source_record_id) is None:
                problems.append(
                    f"requirement {requirement.id} -> unknown source {citation.source_record_id}"
                )
        for class_id in requirement.accepted_document_class_ids:
            if class_id not in document_class_id_set:
                problems.append(
                    f"requirement {requirement.id} -> unknown document class {class_id}"
                )
        # §5.4 gives two independent reasons a requirement cannot be waived: it
        # is a statutory prohibition, or waiving it would turn absent evidence
        # into a fact. So non-waivable does not imply STATUTORY. What it does
        # imply is that no role may override the blocker — OFFICE_POLICY and
        # PROFESSIONAL_JUDGMENT are overridable by definition (§7.3), so a
        # non-waivable requirement carrying one of them would be waivable in
        # practice through a different door.
        if not requirement.waivable and requirement.unsatisfied_blocker_kind in _OVERRIDABLE_KINDS:
            problems.append(
                f"requirement {requirement.id} is non-waivable but its blocker kind is "
                f"{requirement.unsatisfied_blocker_kind.value}, which a role may override"
            )

    for check in checks_mod.CHECK_DEFINITIONS:
        for fact_type_id in check.input_fact_type_ids:
            if fact_type_id not in fact_type_ids:
                problems.append(f"check {check.id} -> unknown fact type {fact_type_id}")
        for citation in check.sources:
            if get_source_record(citation.source_record_id) is None:
                problems.append(f"check {check.id} -> unknown source {citation.source_record_id}")

    for question in questions_mod.ALL_QUESTIONS:
        for module_id in question.activates_module_ids:
            if module_id not in conditional_ids:
                problems.append(f"question {question.id} -> unknown conditional module {module_id}")

    for template in forms_mod.FORM_TEMPLATES:
        for subtype_id in template.subtype_ids:
            if subtype_id not in subtype_id_set:
                problems.append(f"template {template.id} -> unknown subtype {subtype_id}")
        for mapping in template.field_mappings:
            if mapping.fact_type_id is not None and mapping.fact_type_id not in fact_type_ids:
                problems.append(
                    f"template {template.id} field {mapping.field_id} -> unknown fact type "
                    f"{mapping.fact_type_id}"
                )

    # The namespace separation the spec calls out by name (§Executive 11).
    gazette_31 = forms_mod.get_template("rta.reg.2022.form.31")
    ops_31 = forms_mod.get_template("rta.ops.tire.31")
    if gazette_31 is None or ops_31 is None:
        problems.append(
            "both rta.reg.2022.form.31 (register an address) and rta.ops.tire.31 "
            "(apply for a new Title Certificate) must exist"
        )
    elif gazette_31.namespace is ops_31.namespace:
        problems.append(
            "rta.reg.2022.form.31 and rta.ops.tire.31 share a namespace; they are "
            "different forms and must not be interchangeable"
        )

    if problems:
        raise RulePackIntegrityError("; ".join(problems))
