"""Strict validation of the actual handler's closed, typed declaration."""

from typing import Any, Literal, cast

from pydantic import ConfigDict, Field, create_model

from src.modules.matter_agent.ports import ToolDeclaration


def validate_arguments(declaration: ToolDeclaration, arguments: dict[str, Any]) -> dict[str, Any]:
    schema = declaration.parameters
    fields: dict[str, Any] = {}
    required = schema.get("required", [])
    for name, prop in schema.get("properties", {}).items():
        types: dict[str, Any] = {
            "string": str,
            "integer": int,
            "boolean": bool,
            "number": float,
            "array": list[str],
        }
        annotation = types[prop["type"]]
        if "enum" in prop:
            annotation = Literal[tuple(prop["enum"])]
        default = ... if name in required else None
        if default is None:
            annotation = annotation | None
        fields[name] = (
            annotation,
            Field(default=default, ge=prop.get("minimum"), max_length=prop.get("maxLength")),
        )
    model = create_model(
        "ToolArguments", __config__=ConfigDict(strict=True, extra="forbid"), **fields
    )
    return cast(dict[str, Any], model.model_validate(arguments).model_dump(exclude_unset=True))
