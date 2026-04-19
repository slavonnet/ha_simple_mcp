"""Unit tests for MCP -> HA proxy translator."""

from __future__ import annotations

from custom_components.ha_simple_mcp.models import ApiEndpoint, ApiParameter
from custom_components.ha_simple_mcp.proxy import _build_request


def _endpoint_get() -> ApiEndpoint:
    return ApiEndpoint(
        method="GET",
        path="/api/states/{entity_id}",
        description="Get state",
        returns_description="state",
        parameters=(
            ApiParameter(
                name="entity_id",
                required=True,
                description="Entity id",
                schema_type="string",
                in_path=True,
            ),
            ApiParameter(
                name="limit",
                required=False,
                description="Limit",
                schema_type="integer",
            ),
        ),
        scope="ha.api.get.api.states",
    )


def _endpoint_post() -> ApiEndpoint:
    return ApiEndpoint(
        method="POST",
        path="/api/services/light/turn_on",
        description="Call service",
        returns_description="result",
        parameters=(
            ApiParameter(
                name="entity_id",
                required=True,
                description="Entity id",
                schema_type="string",
            ),
            ApiParameter(
                name="brightness",
                required=False,
                description="Brightness",
                schema_type="integer",
            ),
        ),
        scope="ha.api.post.api.services.light.turn_on",
    )


def test_build_request_get():
    endpoint = _endpoint_get()
    path, body, query = _build_request(endpoint, {"entity_id": "light.kitchen", "limit": 2})

    assert path == "/api/states/light.kitchen"
    assert body == {}
    assert query == {"limit": 2}


def test_build_request_post():
    endpoint = _endpoint_post()
    path, body, query = _build_request(
        endpoint, {"entity_id": "light.kitchen", "brightness": 200}
    )

    assert path == "/api/services/light/turn_on"
    assert body == {"entity_id": "light.kitchen", "brightness": 200}
    assert query == {}
