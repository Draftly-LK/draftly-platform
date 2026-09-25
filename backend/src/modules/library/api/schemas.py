from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class LegalSourceRead(CamelModel):
    id: str
    title: str
    reference: str
    type: Literal["statute", "amendment"]
    weight: Literal["binding", "unverified-candidate"]
    verified: bool
    section_count: int
    source_url: str
    extraction_confidence: str
    corpus_version: str


class LegalSourceListRead(CamelModel):
    items: list[LegalSourceRead]
    total: int
