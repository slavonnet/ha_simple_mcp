"""Compatibility wrappers for reusable package server module.

Deprecated:
    Import from ``ha_simple_mcp.server`` instead.
"""

from ha_simple_mcp.server import McpHttpServer, normalize_scopes

__all__ = ["McpHttpServer", "normalize_scopes"]
