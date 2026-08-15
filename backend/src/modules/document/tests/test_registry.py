"""Unit tests for the document template registry."""

from __future__ import annotations

from src.modules.document.domain.registry import (
    FORM8_INSTRUMENT,
    OTHER_KIND,
    classification_prompt,
    get_template,
    is_valid_extent,
    is_valid_iso_date,
    is_valid_nic,
    normalize_field_value,
    registered_kinds,
)


class TestRegistry:
    def test_four_templates_registered(self):
        assert registered_kinds() == [
            "form8-instrument",
            "identity-card",
            "survey-plan",
            "title-certificate",
        ]

    def test_unknown_kind_returns_none(self):
        assert get_template("deed") is None
        assert get_template(OTHER_KIND) is None

    def test_classification_prompt_is_generated_from_registry(self):
        prompt = classification_prompt()
        for kind in registered_kinds():
            assert f'"{kind}"' in prompt
        assert f'"{OTHER_KIND}"' in prompt
        assert "never guess" in prompt

    def test_field_keys_match_the_form_contract_vocabulary(self):
        """The registry must speak the frontend factBinding vocabulary — one
        contract for extraction, drafting gate, and rendering."""
        form8_keys = set(FORM8_INSTRUMENT.field_keys())
        assert {
            "district",
            "dsDivision",
            "cadastralMapNo",
            "parcelNo",
            "extent",
            "titleCertificateNo",
            "transferorName",
            "transfereeNic",
            "consideration",
            "notaryCode",
        } <= form8_keys


class TestNormalization:
    def test_null_tokens_collapse_to_none(self):
        for token in ("", "  ", "null", "None", "N/A", "unknown", "UNDETECTED"):
            assert normalize_field_value(token) is None

    def test_real_values_survive_with_whitespace_stripped(self):
        assert normalize_field_value("  945873370V ") == "945873370V"

    def test_normalize_fields_covers_all_keys_and_ignores_extras(self):
        raw = {"district": "Colombo", "bogus": "x", "extent": "undetected"}
        out = FORM8_INSTRUMENT.normalize_fields(raw)
        assert out["district"] == "Colombo"
        assert out["extent"] is None
        assert "bogus" not in out
        assert set(out) == set(FORM8_INSTRUMENT.field_keys())


class TestValidators:
    def test_nic_formats(self):
        assert is_valid_nic("945873370V")
        assert is_valid_nic("199452270054")  # 12-digit new format
        assert not is_valid_nic("bad-nic")
        assert not is_valid_nic("12345")

    def test_iso_date(self):
        assert is_valid_iso_date("1994-01-01")
        assert not is_valid_iso_date("01/01/1994")

    def test_extent(self):
        assert is_valid_extent("0.0153 hectares")
        assert is_valid_extent("2 ha")
        assert not is_valid_extent("six perches")

    def test_validate_field_returns_none_without_validator(self):
        assert FORM8_INSTRUMENT.validate_field("district", "Colombo") is None
        assert FORM8_INSTRUMENT.validate_field("transfereeNic", "945873370V") is True
        assert FORM8_INSTRUMENT.validate_field("nonexistent", "x") is None
