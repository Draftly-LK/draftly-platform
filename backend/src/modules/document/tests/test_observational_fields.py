"""Source observations do not imply a party's role in a transaction."""

from src.modules.content_governance.contracts import fact_type_for_field
from src.modules.document.domain.registry import IDENTITY_CARD


def test_nic_uses_holder_observations_and_keeps_every_printed_field():
    keys = {field.key for field in IDENTITY_CARD.fields}
    assert "holderNic" in keys
    assert "transfereeNic" not in keys
    for key in (
        "holderNic",
        "holderNameEn",
        "holderNameSi",
        "holderDateOfBirth",
        "holderAddress",
        "surveyorRegistration",
    ):
        definition = fact_type_for_field(key)
        assert definition is not None, key
        assert "transferee" not in definition.id
