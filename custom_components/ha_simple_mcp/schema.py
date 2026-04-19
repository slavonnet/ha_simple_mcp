"""Schema building and caching for MCP tools."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .models import ApiEndpoint


def build_tool_name(endpoint: ApiEndpoint) -> str:
    """Build stable MCP tool name from endpoint metadata."""
    body = endpoint.path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    if not body:
        body = "root"
    return f"ha_{endpoint.method.lower()}_{body}"


def build_tools_schema(endpoints: list[ApiEndpoint]) -> list[dict[str, Any]]:
    """Build MCP tools schema from discovered endpoints."""
    tools: list[dict[str, Any]] = []
    for endpoint in endpoints:
        required = [param.name for param in endpoint.parameters if param.required]
        properties = {
            param.name: {
                "type": param.schema_type,
                "description": param.description,
            }
            for param in endpoint.parameters
        }
        tools.append(
            {
                "name": build_tool_name(endpoint),
                "description": endpoint.description,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": sorted(required),
                    "additionalProperties": False,
                },
                "returns": {
                    "type": "object",
                    "description": endpoint.returns_description,
                },
                "x-ha-endpoint": {
                    "method": endpoint.method,
                    "path": endpoint.path,
                    "scope": endpoint.scope or "",
                },
            }
        )
    return tools


@dataclass(slots=True)
class SchemaCache:
    """TTL cache for generated tools schema."""

    ttl_seconds: int
    _cache: list[dict[str, Any]] | None = None
    _generated_at: float = 0.0

    async def get_or_build(self, catalog) -> list[dict[str, Any]]:
        """Return cached schema or build and cache a fresh one."""
        cached = self.get()
        if cached is not None:
            return cached
        endpoints = await catalog()
        tools = build_tools_schema(endpoints)
        self.set(tools)
        return tools

    def get(self) -> list[dict[str, Any]] | None:
        """Get cached schema if fresh enough."""
        if self._cache is None:
            return None
        if (time.monotonic() - self._generated_at) > self.ttl_seconds:
            self.invalidate()
            return None
        return self._cache

    def set(self, tools: list[dict[str, Any]]) -> None:
        """Store schema and timestamp."""
        self._cache = tools
        self._generated_at = time.monotonic()

    def invalidate(self) -> None:
        """Drop cached value."""
        self._cache = None
        self._generated_at = 0.0
