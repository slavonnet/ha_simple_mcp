"""Schema validation helpers for MCP tool calls."""

from __future__ import annotations

from typing import Any


class ValidationError(ValueError):
    """Raised when MCP call arguments don't match tool schema."""


def validate_call(endpoint, arguments: dict[str, Any]) -> None:
    """Validate call arguments against endpoint parameters."""
    if not isinstance(arguments, dict):
        raise ValidationError("arguments must be an object")

    by_name = {param.name: param for param in endpoint.parameters}
    required = {param.name for param in endpoint.parameters if param.required}

    missing = sorted(name for name in required if name not in arguments)
    if missing:
        raise ValidationError(f"missing required parameters: {', '.join(missing)}")

    unknown = sorted(name for name in arguments if name not in by_name)
    if unknown:
        raise ValidationError(f"unknown parameters: {', '.join(unknown)}")

    for name, value in arguments.items():
        expected_type = by_name[name].schema_type
        if not _matches_type(expected_type, value):
            raise ValidationError(
                f"invalid parameter '{name}' type: expected {expected_type}"
            )


def _matches_type(expected: str, value: Any) -> bool:
    """Type check for minimal JSON schema subset."""
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True
