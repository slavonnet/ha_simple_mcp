"""Compatibility wrappers for reusable package server module.

Deprecated:
    Import from ``ha_api_mcp.server`` instead.
"""

from ha_api_mcp.server import McpHttpServer, normalize_scopes

__all__ = ["McpHttpServer", "normalize_scopes"]
