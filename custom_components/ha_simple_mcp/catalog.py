"""API endpoint catalog discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import ApiEndpoint, ApiParameter


@dataclass(slots=True)
class ApiCatalog:
    """Catalog of discoverable API endpoints."""

    hass: Any
    _endpoints: list[ApiEndpoint] | None = None

    async def discover(self) -> list[ApiEndpoint]:
        """Discover API routes from Home Assistant HTTP component."""
        if self._endpoints is None:
            self._endpoints = await _discover_api_endpoints(self.hass)
        return self._endpoints

    async def get_by_tool_name(self, tool_name: str) -> ApiEndpoint | None:
        """Resolve endpoint by generated tool name."""
        for endpoint in await self.discover():
            if endpoint.tool_name == tool_name:
                return endpoint
        return None


async def _discover_api_endpoints(hass: Any) -> list[ApiEndpoint]:
    """Discover API routes from Home Assistant HTTP component.

    Home Assistant does not expose a complete OpenAPI contract for all dynamic routes.
    This function inspects registered aiohttp routes and creates a normalized catalog.
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
        description = f"Call Home Assistant endpoint {method} {path} via {handler_name}."
        endpoints.append(
            ApiEndpoint(
                method=method,
                path=path,
                description=description,
                returns_description="Raw Home Assistant JSON response.",
                parameters=_extract_path_parameters(path),
                scope=_build_scope(method, path),
            )
        )

    unique: dict[tuple[str, str], ApiEndpoint] = {}
    for endpoint in endpoints:
        unique[(endpoint.method, endpoint.path)] = endpoint

    return sorted(unique.values(), key=lambda item: (item.path, item.method))


def _extract_path_parameters(path: str) -> tuple[ApiParameter, ...]:
    """Extract path params from aiohttp formatter-like segments."""
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


def _build_scope(method: str, path: str) -> str:
    """Build default scope expression."""
    normalized = path.strip("/").replace("/", ".")
    return f"ha.api.{method.lower()}.{normalized}"
