from __future__ import annotations

from types import SimpleNamespace

import pytest
from ha_api_mcp.catalog import ApiCatalog, discover_api_endpoints


def _make_route(method: str, path: str, handler_name: str):
    class DummyResource:
        def get_info(self):
            return {"path": path}

    async def _handler():
        return None

    _handler.__name__ = handler_name
    return SimpleNamespace(method=method, resource=DummyResource(), handler=_handler)


@pytest.mark.asyncio
async def test_discover_only_api_routes():
    app = SimpleNamespace(
        router=SimpleNamespace(
            routes=lambda: [
                _make_route("GET", "/api/states", "states"),
                _make_route("POST", "/api/services/{domain}/{service}", "service"),
                _make_route("GET", "/not-api", "skip"),
            ]
        )
    )
    hass = SimpleNamespace(http=SimpleNamespace(app=app))

    endpoints = await discover_api_endpoints(hass)

    assert len(endpoints) == 2
    assert all(endpoint.path.startswith("/api/") for endpoint in endpoints)
    service_endpoint = next(
        endpoint for endpoint in endpoints if endpoint.path == "/api/services/{domain}/{service}"
    )
    assert service_endpoint.parameters[0].name == "domain"
    assert service_endpoint.parameters[1].name == "service"

@pytest.mark.asyncio
async def test_discover_skips_non_string_paths() -> None:
    class DummyResource:
        def get_info(self):
            return {"path": 123}

    async def _handler():
        return None

    route = SimpleNamespace(method="GET", resource=DummyResource(), handler=_handler)
    app = SimpleNamespace(router=SimpleNamespace(routes=lambda: [route]))
    hass = SimpleNamespace(http=SimpleNamespace(app=app))

    endpoints = await discover_api_endpoints(hass)
    assert endpoints == []


@pytest.mark.asyncio
async def test_catalog_cache_and_lookup() -> None:
    app = SimpleNamespace(
        router=SimpleNamespace(
            routes=lambda: [
                _make_route("GET", "/api/states", "states"),
            ]
        )
    )
    hass = SimpleNamespace(http=SimpleNamespace(app=app))
    catalog = ApiCatalog(hass=hass)

    first = await catalog.discover()
    second = await catalog.discover()
    assert first is second

    endpoint = await catalog.get_by_tool_name(first[0].tool_name)
    assert endpoint is not None
    assert endpoint.path == "/api/states"

    missing = await catalog.get_by_tool_name("ha_get_missing")
    assert missing is None


@pytest.mark.asyncio
async def test_discover_handles_routes_without_path_info() -> None:
    route = SimpleNamespace(
        method="GET",
        resource=SimpleNamespace(get_info=lambda: {}),
        handler=SimpleNamespace(__name__="empty"),
    )
    app = SimpleNamespace(router=SimpleNamespace(routes=lambda: [route]))
    hass = SimpleNamespace(http=SimpleNamespace(app=app))

    endpoints = await discover_api_endpoints(hass)
    assert endpoints == []


@pytest.mark.asyncio
async def test_discover_handles_missing_http_component() -> None:
    hass = SimpleNamespace(http=None)
    endpoints = await discover_api_endpoints(hass)
    assert endpoints == []
