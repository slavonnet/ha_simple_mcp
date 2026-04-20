"""Compatibility wrappers for reusable package server module.

Deprecated:
    Import from ``ha_api_mcp.server`` instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import web
from ha_api_mcp.server import McpHttpServer as _CoreMcpHttpServer
from ha_api_mcp.server import normalize_scopes

_GENERIC_DESCRIPTION_PREFIX = "Call Home Assistant endpoint"


class McpHttpServer(_CoreMcpHttpServer):
    """Adapter server that keeps MCP tools payload compact."""

    async def _handle_tools(self, request: web.Request) -> web.Response:
        """Handle tools listing request with compact metadata output."""
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)

        tools = await self._schema_cache.get_or_build(self._catalog.discover)
        compact_tools = [_compact_tool(tool) for tool in tools]
        return web.json_response({"tools": compact_tools})


def _compact_tool(tool: Mapping[str, Any]) -> dict[str, Any]:
    """Drop verbose metadata and expose compact scope field."""
    compact: dict[str, Any] = {}
    for key, value in tool.items():
        if key == "x-ha-endpoint":
            continue
        if (
            key == "description"
            and isinstance(value, str)
            and value.startswith(_GENERIC_DESCRIPTION_PREFIX)
        ):
            continue
        compact[key] = value

    scope = _extract_compact_scope(tool)
    if scope:
        compact["x-scope"] = scope
    return compact


def _extract_compact_scope(tool: Mapping[str, Any]) -> str:
    """Get compact scope string from original x-ha-endpoint metadata."""
    endpoint_meta = tool.get("x-ha-endpoint")
    if not isinstance(endpoint_meta, Mapping):
        return ""

    scope = endpoint_meta.get("scope")
    if not isinstance(scope, str):
        return ""

    return _shorten_scope(scope)


def _shorten_scope(scope: str) -> str:
    """Shorten `ha.api.<method>.api.*` scope to `<method>.*`."""
    if not scope:
        return ""

    parts = [part for part in scope.split(".") if part]
    has_ha_prefix = len(parts) >= 2 and parts[0] == "ha" and parts[1] == "api"
    if has_ha_prefix:
        parts = parts[2:]
        if len(parts) >= 2 and parts[1] == "api":
            parts = [parts[0], *parts[2:]]

    return ".".join(parts)


__all__ = ["McpHttpServer", "normalize_scopes"]
