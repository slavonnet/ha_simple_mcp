"""Backwards-compatible imports for HA integration layer.

The implementation now lives in the reusable Python package `ha_api_mcp`.
Deprecated:
    Import from `ha_api_mcp.models` instead.
"""

from ha_api_mcp.models import (
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
