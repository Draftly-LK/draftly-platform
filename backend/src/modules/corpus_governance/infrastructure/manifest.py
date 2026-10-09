"""Canonical signed release validation and metadata reads; no network or writes."""

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import cast
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.modules.corpus_governance.application.releases import assemble_release
from src.modules.corpus_governance.contracts import (
    AuthorityMetadata,
    AuthorityRelationship,
    PublicationDenied,
    ReleaseIntegrityError,
    ReleaseUnavailableError,
)
from src.modules.corpus_governance.domain.models import (
    AudiencePolicy,
    ContentApproval,
    CorpusAudience,
    LegalSource,
    ReleasedSource,
    ReviewApproval,
    SourceInput,
    ValidatedRelease,
)
from src.modules.corpus_governance.domain.policies import validate_source

SCHEMA_VERSION = "legal-source-release-v1"
RELEASE_PREFIX = "legal-sources-v1:"


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ReleaseIntegrityError("Expected a manifest object")
    return cast(dict[str, object], value)


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ReleaseIntegrityError("Expected a manifest array")
    return cast(list[object], value)


def _string(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise ReleaseIntegrityError("Expected a nonblank manifest string")
    return value


def _optional_string(value: object) -> str | None:
    return None if value is None else _string(value)


def _choice[T: str](value: object, allowed: tuple[T, ...]) -> T:
    text = _string(value)
    for option in allowed:
        if text == option:
            return option
    raise ReleaseIntegrityError("Unknown manifest policy or metadata value")


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise ReleaseIntegrityError("Expected an explicit manifest boolean")
    return value


def _page(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 1:
        raise ReleaseIntegrityError("Page locator must be a positive integer")
    return value


def _date(value: object) -> date | None:
    if value is None:
        return None
    text = _string(value)
    parsed = date.fromisoformat(text)
    if parsed.isoformat() != text:
        raise ReleaseIntegrityError("Dates must use YYYY-MM-DD")
    return parsed


def _timestamp(value: object) -> datetime:
    parsed = datetime.fromisoformat(_string(value))
    if parsed.utcoffset() is None:
        raise ReleaseIntegrityError("Timestamp timezone is required")
    return parsed


def _sha(value: object) -> str:
    text = _string(value)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ReleaseIntegrityError("Expected a lowercase SHA-256 digest")
    return text


def _url(value: object) -> str:
    text = _string(value)
    parsed = urlsplit(text)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or "\\" in text
        or any(c.isspace() or ord(c) == 127 for c in text)
    ):
        raise ReleaseIntegrityError("Source URL must be a recorded safe HTTP(S) link")
    return text


def _approval(value: object) -> ReviewApproval:
    record = _object(value)
    return ReviewApproval(
        _string(record["reference"]),
        _string(record["reviewedBy"]),
        _timestamp(record["reviewedAt"]),
    )


def _input(value: object) -> SourceInput:
    record = _object(value)
    return SourceInput(_string(record["path"]), _sha(record["sha256"]))


def _relationship(value: object) -> AuthorityRelationship:
    record = _object(value)
    return AuthorityRelationship(
        relation=_choice(record["relation"], ("amends", "supersedes", "made-under", "commences")),
        target_source_id=_string(record["targetSourceId"]),
        target_reference=_optional_string(record.get("targetReference")),
        supporting_page=_page(record.get("supportingPage")),
        review_state=_choice(record["reviewState"], ("unreviewed", "reviewed")),
    )


def _source(value: object, version: str) -> LegalSource:
    record = _object(value)
    original = _input(record["original"])
    indexed = _input(record["indexed"]) if record.get("indexed") is not None else None
    policy = _object(record["policy"])
    content = _object(record["contentApproval"])
    metadata = AuthorityMetadata(
        source_id=_string(record["sourceId"]),
        title=_string(record["title"]),
        reference=_string(record["reference"]),
        kind=_choice(record["kind"], ("statute", "amendment", "gazette")),
        source_url=_url(record["sourceUrl"]),
        source_sha256=original.sha256,
        publication_date=_date(record.get("publicationDate")),
        effective_from=_date(record.get("effectiveFrom")),
        effective_to=_date(record.get("effectiveTo")),
        commencement_known=_boolean(record["commencementKnown"]),
        commencement_source_id=_optional_string(record.get("commencementSourceId")),
        commencement_page=_page(record.get("commencementPage")),
        relationships=tuple(_relationship(item) for item in _array(record["relationships"])),
        release_version=version,
        review_state=_choice(
            record["reviewState"],
            (
                "discovered",
                "provenance-recorded",
                "rights-reviewed",
                "content-reviewed",
                "approved",
                "quarantined",
                "retired",
            ),
        ),
        currency_status=_choice(
            record["currencyStatus"], ("current", "superseded", "reverify", "unknown")
        ),
    )
    return LegalSource(
        metadata=metadata,
        original=original,
        indexed=indexed,
        publication_body=_string(record["publicationBody"]),
        source_publisher=_string(record["sourcePublisher"]),
        language=_string(record["language"]),
        retrieved_at=_timestamp(record["retrievedAt"]),
        official_text=_boolean(record["officialText"]),
        official_translation=_boolean(record["officialTranslation"]),
        provenance_status=_choice(
            record["provenanceStatus"],
            ("verified-official", "verified-licensed", "verified-public-domain", "unverified"),
        ),
        rights_status=_choice(
            record["rightsStatus"],
            ("official-text", "licensed", "public-domain", "restricted", "unknown"),
        ),
        source_use_class=_choice(
            record["sourceUseClass"],
            ("public-catalogue", "restricted-internal-research", "quarantined"),
        ),
        licence_reference=_optional_string(record.get("licenceReference")),
        rights_approval=_approval(record["rightsApproval"]),
        content_approval=ContentApproval(
            _approval(content),
            _sha(content["sourceSha256"]),
            _sha(content["indexedSha256"]) if content.get("indexedSha256") is not None else None,
        ),
        policy=AudiencePolicy(
            audience=_choice(policy["audience"], ("internal-research", "public-catalogue")),
            indexing=_choice(policy["indexing"], ("full-text", "metadata-only", "blocked")),
            display=_choice(
                policy["display"],
                ("full-text", "snippet-only", "metadata-only", "link-out", "blocked"),
            ),
            quotation=_choice(
                policy["quotation"], ("approved-span", "short-quotation-only", "blocked")
            ),
            download=_choice(
                policy["download"], ("source-file", "link-to-official-source", "blocked")
            ),
            approval=_approval(policy["approval"]),
        ),
    )


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseIntegrityError("Duplicate manifest object key")
        result[key] = value
    return result


def _reject_number(value: str) -> object:
    raise ReleaseIntegrityError("Noninteger JSON numbers are not supported")


def canonical_manifest_bytes(value: object) -> bytes:
    """The v1 wire encoding: UTF-8, sorted keys, no whitespace or nonfinite values."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _read_input(root: Path, source_input: SourceInput) -> bytes:
    name = source_input.path
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {".", ".."} for part in name.split("/"))
        or "\\" in name
        or ":" in name
        or "\x00" in name
    ):
        raise ReleaseIntegrityError("Source path must be relative and contained")
    target = root.joinpath(*path.parts)
    # Refuse symlinks entirely, including contained links, to avoid ambiguous inputs.
    cursor = root
    for part in path.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ReleaseIntegrityError("Source paths cannot contain symlinks")
    resolved = target.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ReleaseIntegrityError("Source file is outside the release root")
    content = resolved.read_bytes()
    if hashlib.sha256(content).hexdigest() != source_input.sha256:
        raise ReleaseIntegrityError("Source checksum differs from reviewed bytes")
    return content


def validate_release(
    manifest_bytes: bytes,
    signature: bytes,
    trusted_public_key: bytes | None,
    audience: CorpusAudience,
    source_root: Path,
) -> ValidatedRelease:
    """Verify with a caller-trusted raw Ed25519 key; no key is read from the envelope."""
    if trusted_public_key is None:
        raise ReleaseUnavailableError("A trusted release signing key is required")
    try:
        Ed25519PublicKey.from_public_bytes(trusted_public_key).verify(signature, manifest_bytes)
        decoded: object = json.loads(
            manifest_bytes.decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
        if canonical_manifest_bytes(decoded) != manifest_bytes:
            raise ReleaseIntegrityError("Release manifest is not canonical UTF-8 JSON")
        envelope = _object(decoded)
        if set(envelope) != {"schemaVersion", "audience", "sources"}:
            raise ReleaseIntegrityError("Unexpected release envelope fields")
        if envelope["schemaVersion"] != SCHEMA_VERSION:
            raise ReleaseIntegrityError("Unsupported release schema")
        release_audience = _choice(envelope["audience"], ("internal-research", "public-catalogue"))
        if release_audience != audience:
            raise PublicationDenied("Release audience does not match requested audience")
        version = RELEASE_PREFIX + hashlib.sha256(manifest_bytes).hexdigest()
        root = source_root.resolve(strict=True)
        if not root.is_dir():
            raise ReleaseUnavailableError("Release source root is unavailable")
        entries: list[ReleasedSource] = []
        seen: set[str] = set()
        for value in _array(envelope["sources"]):
            source = _source(value, version)
            if source.metadata.source_id in seen:
                raise ReleaseIntegrityError("Duplicate source ID")
            seen.add(source.metadata.source_id)
            validate_source(source, release_audience)
            _read_input(root, source.original)
            indexed_content = _read_input(root, source.indexed) if source.indexed else None
            if indexed_content is not None:
                indexed_content.decode("utf-8")
            entries.append(ReleasedSource(source, indexed_content))
        return assemble_release(version, release_audience, tuple(entries))
    except ReleaseUnavailableError:
        raise
    except InvalidSignature:
        raise ReleaseIntegrityError("Release signature is invalid") from None
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise ReleaseIntegrityError("Release metadata or source input is invalid") from None


class ManifestAuthorityReader:
    """Metadata projection over one validated audience; wrong version never falls back."""

    def __init__(self, release: ValidatedRelease) -> None:
        self._release = release

    def _records(self, release_version: str) -> tuple[AuthorityMetadata, ...]:
        if release_version != self._release.release_version:
            raise ReleaseUnavailableError("Authority metadata release mismatch")
        return tuple(entry.source.metadata for entry in self._release.sources)

    async def authorities(
        self, source_ids: tuple[str, ...], *, release_version: str
    ) -> tuple[AuthorityMetadata, ...]:
        requested = set(source_ids)
        return tuple(
            record for record in self._records(release_version) if record.source_id in requested
        )

    async def related(
        self, source_ids: tuple[str, ...], *, release_version: str
    ) -> tuple[AuthorityMetadata, ...]:
        records = self._records(release_version)
        permitted = {record.source_id for record in records}
        requested = set(source_ids) & permitted
        related_ids: set[str] = set()
        for record in records:
            for relation in record.relationships:
                if relation.review_state != "reviewed":
                    continue
                if record.source_id in requested:
                    related_ids.add(relation.target_source_id)
                if relation.target_source_id in requested:
                    related_ids.add(record.source_id)
        # Return original records, preserving the direction and locators of every edge.
        return tuple(record for record in records if record.source_id in related_ids - requested)
