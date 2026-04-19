"""Schema building and caching utilities for MCP tools."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .models import ApiEndpoint


def build_tool_name(endpoint: ApiEndpoint) -> str:
    """Build stable MCP tool name from endpoint metadata.

    Args:
        endpoint: Endpoint definition used to derive the tool name.

    Returns:
        Deterministic tool name in the form ``ha_<method>_<path>``.
    """
    body = endpoint.path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    if not body:
        body = "root"
    return f"ha_{endpoint.method.lower()}_{body}"


def build_tools_schema(endpoints: list[ApiEndpoint]) -> list[dict[str, Any]]:
    """Build MCP tools schema from discovered endpoints.

    Args:
        endpoints: Endpoint list discovered from Home Assistant runtime.

    Returns:
        List with MCP tool descriptors compatible with JSON payload transport.
    """
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
    """TTL cache for generated tools schema.

    Args:
        ttl_seconds: Cache lifetime in seconds.

    Returns:
        SchemaCache: Cache object for MCP tools schema.
    """

    ttl_seconds: int
    _cache: list[dict[str, Any]] | None = None
    _generated_at: float = 0.0

    async def get_or_build(
        self,
        fetch_endpoints: Callable[[], Awaitable[list[ApiEndpoint]]],
    ) -> list[dict[str, Any]]:
        """Return cached schema or build and cache a fresh one.

        Args:
            fetch_endpoints: Async callable returning endpoint list.

        Returns:
            Cached or freshly generated tools schema.
        """
        cached = self.get()
        if cached is not None:
            return cached
        endpoints = await fetch_endpoints()
        tools = build_tools_schema(endpoints)
        self.set(tools)
        return tools

    def get(self) -> list[dict[str, Any]] | None:
        """Get cached schema if fresh enough.

        Returns:
            Cached schema if cache is present and valid, else ``None``.
        """
        if self._cache is None:
            return None
        if (time.monotonic() - self._generated_at) > self.ttl_seconds:
            self.invalidate()
            return None
        return self._cache

    def set(self, tools: list[dict[str, Any]]) -> None:
        """Store schema and timestamp.

        Args:
            tools: Generated tools schema to cache.

        Returns:
            None: Cache value is updated in place.
        """
        self._cache = tools
        self._generated_at = time.monotonic()

    def invalidate(self) -> None:
        """Drop cached value immediately.

        Returns:
            None: Cache storage is cleared in place.
        """
        self._cache = None
        self._generated_at = 0.0
