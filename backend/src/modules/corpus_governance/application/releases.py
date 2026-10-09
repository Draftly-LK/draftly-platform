"""Assemble a policy-checked immutable release from verified infrastructure inputs."""

from src.modules.corpus_governance.contracts import ReleaseIntegrityError
from src.modules.corpus_governance.domain.models import (
    CorpusAudience,
    ReleasedSource,
    ValidatedRelease,
)
from src.modules.corpus_governance.domain.policies import validate_source


def assemble_release(
    release_version: str, audience: CorpusAudience, sources: tuple[ReleasedSource, ...]
) -> ValidatedRelease:
    seen: set[str] = set()
    for entry in sources:
        source = entry.source
        if source.metadata.source_id in seen or source.metadata.release_version != release_version:
            raise ReleaseIntegrityError("Duplicate source or inconsistent release identity")
        seen.add(source.metadata.source_id)
        validate_source(source, audience)
        if (source.indexed is None) != (entry.indexed_content is None):
            raise ReleaseIntegrityError("Missing or unexpected verified index input")
    return ValidatedRelease(release_version, audience, sources)
