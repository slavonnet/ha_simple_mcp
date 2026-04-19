"""Validation helpers for MCP tool calls."""

from __future__ import annotations

from typing import Any

from .models import ApiEndpoint


class ValidationError(ValueError):
    """Raised when MCP call arguments do not match endpoint schema."""


def validate_call(endpoint: ApiEndpoint, arguments: dict[str, Any]) -> None:
    """Validate call arguments against endpoint parameter schema.

    Parameters
    ----------
    endpoint:
        Endpoint metadata including parameter definitions.
    arguments:
        Input arguments received from the MCP request.

    Returns
    -------
    None
        Function returns `None` when validation succeeds.

    Raises
    ------
    ValidationError
        If arguments are not an object, required fields are missing,
        unknown arguments are provided, or type mismatch is detected.
    """

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
        if not matches_type(expected_type, value):
            raise ValidationError(
                f"invalid parameter '{name}' type: expected {expected_type}"
            )


def matches_type(expected: str, value: Any) -> bool:
    """Check if value matches expected JSON-like type.

    Parameters
    ----------
    expected:
        Expected type name (`string`, `integer`, `number`, `boolean`, `array`,
        `object`).
    value:
        Runtime value to validate.

    Returns
    -------
    bool
        `True` if value matches expected type, `False` otherwise.
    """

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
