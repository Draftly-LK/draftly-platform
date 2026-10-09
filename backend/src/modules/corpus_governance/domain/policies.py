"""Framework-independent publication checks. Acquisition grants no permission."""

from src.modules.corpus_governance.contracts import PublicationDenied
from src.modules.corpus_governance.domain.models import CorpusAudience, LegalSource


def validate_source(source: LegalSource, audience: CorpusAudience) -> None:
    metadata, policy = source.metadata, source.policy
    if (
        metadata.review_state != "approved"
        or source.source_use_class == "quarantined"
        or source.provenance_status == "unverified"
        or source.rights_status == "unknown"
        or policy.audience != audience
        or policy.indexing == "blocked"
    ):
        raise PublicationDenied("Source is not approved for this release")
    for approval in (
        source.rights_approval,
        source.content_approval.decision,
        policy.approval,
    ):
        if not approval.reference.strip() or not approval.reviewed_by.strip():
            raise PublicationDenied("Independent review record is incomplete")
        if approval.reviewed_at.utcoffset() is None:
            raise PublicationDenied("Review timestamp must identify its timezone")
    if source.rights_status in {"licensed", "restricted"} and not source.licence_reference:
        raise PublicationDenied("Written rights permission is required")
    if source.rights_status == "official-text" and (
        source.provenance_status != "verified-official" or not source.official_text
    ):
        raise PublicationDenied("Official text requires reviewed official provenance")
    if source.rights_status == "licensed" and source.provenance_status != "verified-licensed":
        raise PublicationDenied("Licensed text requires reviewed licensed provenance")
    if (
        source.rights_status == "public-domain"
        and source.provenance_status != "verified-public-domain"
    ):
        raise PublicationDenied("Public-domain text requires reviewed provenance")
    if audience == "public-catalogue" and (
        source.source_use_class != "public-catalogue"
        or source.rights_status == "restricted"
        or policy.display == "blocked"
    ):
        raise PublicationDenied("Source cannot enter the public catalogue")
    if source.source_use_class == "restricted-internal-research" and (
        policy.display in {"full-text", "snippet-only"} or policy.download == "source-file"
    ):
        raise PublicationDenied("Restricted source text cannot be displayed or downloaded")
    indexed_sha = source.indexed.sha256 if source.indexed else None
    if (
        source.original.sha256 != metadata.source_sha256
        or source.content_approval.source_sha256 != source.original.sha256
        or source.content_approval.indexed_sha256 != indexed_sha
    ):
        raise PublicationDenied("Content approval does not cover the exact source and derivative")
    if (policy.indexing == "full-text") != (source.indexed is not None):
        raise PublicationDenied("Index input must match the exact approved indexing policy")
    if metadata.commencement_known != (metadata.effective_from is not None):
        raise PublicationDenied("Unknown commencement cannot acquire an effective date")
    if metadata.commencement_known and (
        not metadata.commencement_source_id or metadata.commencement_page is None
    ):
        raise PublicationDenied("Known commencement requires its reviewed source locator")
    if (
        metadata.effective_from is not None
        and metadata.effective_to is not None
        and metadata.effective_to < metadata.effective_from
    ):
        raise PublicationDenied("Effective date interval is invalid")
