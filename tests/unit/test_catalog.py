from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.ha_simple_mcp.catalog import _discover_api_endpoints


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

    endpoints = await _discover_api_endpoints(hass)

    assert len(endpoints) == 2
    assert all(endpoint.path.startswith("/api/") for endpoint in endpoints)
    service_endpoint = next(
        endpoint for endpoint in endpoints if endpoint.path == "/api/services/{domain}/{service}"
    )
    assert service_endpoint.parameters[0].name == "domain"
    assert service_endpoint.parameters[1].name == "service"
