"""API conventions for the party router — api-conventions.md §2, §3, §5.

The router is exercised through its helpers and its registered routes rather
than an HTTP client: `get_request_context` requires a database session and this
repository has no database-backed test harness yet.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.modules.party.api.router import _require_if_match, router
from src.platform.errors import (
    DraftlyError,
    PreconditionFailedError,
    PreconditionRequiredError,
    make_error_response,
)
from src.platform.pagination import (
    MAX_PAGE_LIMIT,
    Cursor,
    InvalidCursorError,
    InvalidLimitError,
    decode_cursor,
    encode_cursor,
    normalise_limit,
)


class TestConditionalRequests:
    def test_a_missing_if_match_is_428(self):
        with pytest.raises(PreconditionRequiredError) as excinfo:
            _require_if_match(None)
        assert excinfo.value.http_status == 428

    def test_an_unparseable_if_match_is_412_not_500(self):
        with pytest.raises(PreconditionFailedError) as excinfo:
            _require_if_match("not-a-version")
        assert excinfo.value.http_status == 412

    def test_quoted_and_weak_etags_are_accepted(self):
        assert _require_if_match('"7"') == 7
        assert _require_if_match('W/"7"') == 7
        assert _require_if_match(" 7 ") == 7

    def test_every_versioned_mutation_requires_if_match(self):
        versioned = {
            ("PATCH", "/api/v1/parties/{party_id}"),
            (
                "POST",
                "/api/v1/parties/{party_id}/identity-evidence/{evidence_id}/verification",
            ),
            ("POST", "/api/v1/parties/merges"),
        }
        for route in router.routes:
            path = f"/api/v1{route.path}"  # type: ignore[attr-defined]
            for method in route.methods:  # type: ignore[attr-defined]
                if (method, path) not in versioned:
                    continue
                params = route.dependant.header_params  # type: ignore[attr-defined]
                assert any(p.alias == "If-Match" for p in params), (method, path)


class TestPagination:
    def test_the_limit_is_capped_at_100(self):
        assert MAX_PAGE_LIMIT == 100
        assert normalise_limit(100) == 100
        assert normalise_limit(None) == 50
        for bad in (0, -1, 101, 1000):
            with pytest.raises(InvalidLimitError):
                normalise_limit(bad)

    def test_a_cursor_round_trips(self):
        cursor = Cursor(created_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC), id="pty_demo")
        decoded = decode_cursor(encode_cursor(cursor))
        assert decoded is not None
        assert decoded.id == cursor.id
        assert decoded.created_at == cursor.created_at

    def test_a_malformed_cursor_is_a_400_not_a_500(self):
        with pytest.raises(InvalidCursorError) as excinfo:
            decode_cursor("!!!not-base64!!!")
        assert excinfo.value.http_status == 400

    def test_an_absent_cursor_is_the_first_page(self):
        assert decode_cursor(None) is None
        assert decode_cursor("") is None


class TestErrorEnvelope:
    def test_every_party_error_maps_to_a_catalogue_code(self):
        from src.modules.party.domain import errors as party_errors

        expected = {
            party_errors.IdentityPurposeRequiredError: ("identity_purpose_required", 422),
            party_errors.BeneficialOwnerCycleError: ("beneficial_owner_cycle", 422),
            party_errors.BeneficialOwnerDepthExceededError: (
                "beneficial_owner_depth_exceeded",
                422,
            ),
            party_errors.EvidenceNotPinnedError: ("evidence_not_pinned", 422),
            party_errors.EvidenceStateTransitionError: (
                "evidence_state_transition_invalid",
                422,
            ),
            party_errors.MergedPartyImmutableError: ("party_merged", 422),
            party_errors.MergeTargetInvalidError: ("merge_target_invalid", 422),
            party_errors.CrossUserPartyError: ("not_found", 404),
            party_errors.RestrictedComplianceError: ("not_found", 404),
        }
        for error_type, (code, status) in expected.items():
            error = error_type()
            assert (error.code, error.http_status) == (code, status), error_type

    def test_the_envelope_echoes_the_correlation_id(self):
        response = make_error_response(
            DraftlyError("An unexpected error occurred."), correlation_id="corr_party_test"
        )
        assert b"corr_party_test" in response.body
        assert b'"error"' in response.body

    def test_a_refusal_body_names_no_party(self):
        from src.modules.party.domain.errors import RestrictedComplianceError
        from src.platform.privacy import find_private_content

        response = make_error_response(RestrictedComplianceError(), correlation_id="corr_x")
        assert find_private_content(response.body.decode("utf-8")) == []
        assert b"screening" not in response.body.lower()
