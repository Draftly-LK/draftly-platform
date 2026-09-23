"""Loads the service registry the conformance suite is parameterised over."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

BACKEND = Path(__file__).resolve().parents[2]
REGISTRY: list[dict[str, Any]] = yaml.safe_load(
    (BACKEND / "contracts" / "services.yaml").read_text(encoding="utf-8")
)
SERVICE_NAMES = [service["name"] for service in REGISTRY]

#: service-definition-of-done.md §1: L3 is "functional", the first level at
#: which a service's declared runtime has to exist.
FUNCTIONAL_LEVELS = {"L3", "L4"}
