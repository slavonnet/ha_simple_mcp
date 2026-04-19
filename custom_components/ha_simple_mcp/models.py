"""Backwards-compatible imports for HA integration layer.

The implementation now lives in the reusable Python package `ha_simple_mcp`.
Deprecated:
    Import from `ha_simple_mcp.models` instead.
"""

from ha_simple_mcp.models import (
    ApiEndpoint,
    ApiParameter,
    McpSettings,
    ToolCallResult,
    normalize_scope_list,
)

__all__ = [
    "ApiEndpoint",
    "ApiParameter",
    "McpSettings",
    "ToolCallResult",
    "normalize_scope_list",
]
