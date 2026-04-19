"""Endpoint catalog discovery for Home Assistant API routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import ApiEndpoint, ApiParameter


@dataclass(slots=True)
class ApiCatalog:
    """Cache and query discoverable Home Assistant API endpoints.

    Args:
        hass: Home Assistant instance or compatible object exposing `http.app.router`.

    Attributes:
        hass: Home Assistant runtime reference.
        _endpoints: Cached endpoint list built from runtime routes.

    Returns:
        ApiCatalog: Configured catalog instance.
    """

    hass: Any
    _endpoints: list[ApiEndpoint] | None = None

    async def discover(self) -> list[ApiEndpoint]:
        """Discover and cache API endpoints from the HA runtime.

        Returns:
            Sorted list of discoverable API endpoints under `/api`.
        """
        if self._endpoints is None:
            self._endpoints = await discover_api_endpoints(self.hass)
        return self._endpoints

    async def get_by_tool_name(self, tool_name: str) -> ApiEndpoint | None:
        """Find endpoint by deterministic MCP tool name.

        Args:
            tool_name: Tool name generated from endpoint method/path.

        Returns:
            Matching endpoint or `None` if no endpoint maps to the name.
        """
        for endpoint in await self.discover():
            if endpoint.tool_name == tool_name:
                return endpoint
        return None


async def discover_api_endpoints(hass: Any) -> list[ApiEndpoint]:
    """Discover Home Assistant API routes and convert to endpoint models.

    Args:
        hass: Home Assistant instance or compatible runtime object.

    Returns:
        Sorted unique list of API endpoints.
    """
    http = getattr(hass, "http", None)
    app = http.app if http else None
    if app is None:
        return []

    endpoints: list[ApiEndpoint] = []
    for route in app.router.routes():
        resource = route.resource
        raw_info = resource.get_info()
        path = raw_info.get("path") or raw_info.get("formatter")
        if not path or not isinstance(path, str):
            continue
        if not path.startswith("/api"):
            continue

        method = (route.method or "GET").upper()
        handler_name = getattr(route.handler, "__name__", "api_call")
        endpoints.append(
            ApiEndpoint(
                method=method,
                path=path,
                description=f"Call Home Assistant endpoint {method} {path} via {handler_name}.",
                returns_description="Raw Home Assistant JSON response.",
                parameters=extract_path_parameters(path),
                scope=build_scope(method, path),
            )
        )

    unique: dict[tuple[str, str], ApiEndpoint] = {}
    for endpoint in endpoints:
        unique[(endpoint.method, endpoint.path)] = endpoint

    return sorted(unique.values(), key=lambda item: (item.path, item.method))


def extract_path_parameters(path: str) -> tuple[ApiParameter, ...]:
    """Extract path parameters from an aiohttp path template.

    Args:
        path: Route path template potentially containing `{param}` placeholders.

    Returns:
        Tuple of required path parameters.
    """
    params: list[ApiParameter] = []
    for segment in path.split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            raw_name = segment.strip("{}")
            name = raw_name.split(":")[0]
            params.append(
                ApiParameter(
                    name=name,
                    description=f"Path parameter `{name}` for endpoint {path}.",
                    required=True,
                    schema_type="string",
                    in_path=True,
                )
            )
    return tuple(params)


def build_scope(method: str, path: str) -> str:
    """Build deterministic scope identifier for an API endpoint.

    Args:
        method: HTTP method.
        path: Route path.

    Returns:
        Scope string, for example `ha.api.get.api.states`.
    """
    normalized = path.strip("/").replace("/", ".")
    return f"ha.api.{method.lower()}.{normalized}"
