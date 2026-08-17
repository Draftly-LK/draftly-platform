"""Governed-content API router — the RTA rule pack, read-only.

```text
GET /api/v1/rta/rule-pack        everything, with versions
GET /api/v1/rta/taxonomy         families, 22 instruments, processes, services
GET /api/v1/rta/questions        intake question definitions
GET /api/v1/rta/checklist        module and requirement definitions
GET /api/v1/rta/checks           deterministic check definitions
GET /api/v1/rta/forms            template registry and field mappings
GET /api/v1/rta/document-classes controlled document classes
GET /api/v1/rta/sources          source register with verification state
```

There is no write surface. Governed content changes through a reviewed code
change plus counsel approval (§13.2.9 dual approval), not through an endpoint.

Authenticated because the rule pack encodes the office's examination policy,
but not matter-scoped: it contains no client data.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from src.api.deps import get_request_context
from src.modules.content_governance.application.rule_pack_export import (
    checklist_contract,
    checks_contract,
    document_classes_contract,
    forms_contract,
    full_rule_pack_contract,
    questions_contract,
    sources_contract,
    taxonomy_contract,
)
from src.platform.request_context import RequestContext

router = APIRouter(tags=["rta-rule-pack"])


@router.get("/rta/rule-pack")
async def get_rule_pack(ctx: RequestContext = Depends(get_request_context)) -> dict[str, Any]:
    _ = ctx
    return full_rule_pack_contract()


@router.get("/rta/taxonomy")
async def get_taxonomy(ctx: RequestContext = Depends(get_request_context)) -> dict[str, Any]:
    _ = ctx
    return taxonomy_contract()


@router.get("/rta/questions")
async def get_questions(ctx: RequestContext = Depends(get_request_context)) -> dict[str, Any]:
    _ = ctx
    return questions_contract()


@router.get("/rta/checklist")
async def get_checklist(ctx: RequestContext = Depends(get_request_context)) -> dict[str, Any]:
    _ = ctx
    return checklist_contract()


@router.get("/rta/checks")
async def get_checks(ctx: RequestContext = Depends(get_request_context)) -> dict[str, Any]:
    _ = ctx
    return checks_contract()


@router.get("/rta/forms")
async def get_forms(ctx: RequestContext = Depends(get_request_context)) -> dict[str, Any]:
    _ = ctx
    return forms_contract()


@router.get("/rta/document-classes")
async def get_document_classes(
    ctx: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    _ = ctx
    return document_classes_contract()


@router.get("/rta/sources")
async def get_sources(ctx: RequestContext = Depends(get_request_context)) -> dict[str, Any]:
    _ = ctx
    return sources_contract()
