"""Unit tests for MCP -> HA proxy translator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ha_simple_mcp.models import ApiEndpoint, ApiParameter, McpSettings
from ha_simple_mcp.proxy import ApiProxy, ProxyError, build_request


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
    path, body, query = build_request(endpoint, {"entity_id": "light.kitchen", "limit": 2})

    assert path == "/api/states/light.kitchen"
    assert body == {}
    assert query == {"limit": 2}


def test_build_request_post():
    endpoint = _endpoint_post()
    path, body, query = build_request(
        endpoint, {"entity_id": "light.kitchen", "brightness": 200}
    )

    assert path == "/api/services/light/turn_on"
    assert body == {"entity_id": "light.kitchen", "brightness": 200}
    assert query == {}


@pytest.mark.asyncio
async def test_api_proxy_read_only_blocks_non_get() -> None:
    proxy = ApiProxy(
        McpSettings(
            bind_address="",
            port=0,
            auth_token="",
            target_user="owner",
            read_only=True,
            scope_allowlist=(),
            schema_cache_ttl=10,
            timeout=5,
            base_url="http://ha.local",
        )
    )
    endpoint = _endpoint_post()
    with pytest.raises(ProxyError):
        await proxy.call(endpoint, {"entity_id": "light.kitchen"})


@pytest.mark.asyncio
async def test_api_proxy_sets_token_and_json_for_post() -> None:
    proxy = ApiProxy(
        McpSettings(
            bind_address="",
            port=0,
            auth_token="secret",
            target_user="owner",
            read_only=False,
            scope_allowlist=(),
            schema_cache_ttl=10,
            timeout=5,
            base_url="http://ha.local",
        )
    )
    endpoint = _endpoint_post()

    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value={"ok": True})
    response.text = AsyncMock(return_value="ok")

    session = AsyncMock()
    session.__aenter__.return_value = session
    request_cm = MagicMock()
    request_cm.__aenter__ = AsyncMock(return_value=response)
    request_cm.__aexit__ = AsyncMock(return_value=False)
    session.request = MagicMock(return_value=request_cm)

    with patch("ha_simple_mcp.proxy.ClientSession", return_value=session):
        status, body = await proxy.call(endpoint, {"entity_id": "light.kitchen"})

    assert status == 200
    assert body == {"ok": True}
    call = session.request.call_args
    assert call is not None
    assert call.kwargs["headers"]["Authorization"] == "Bearer secret"
    assert call.kwargs["json"]["entity_id"] == "light.kitchen"


@pytest.mark.asyncio
async def test_api_proxy_raises_on_http_error() -> None:
    proxy = ApiProxy(
        McpSettings(
            bind_address="",
            port=0,
            auth_token="",
            target_user="owner",
            read_only=False,
            scope_allowlist=(),
            schema_cache_ttl=10,
            timeout=5,
            base_url="http://ha.local",
        )
    )
    endpoint = _endpoint_get()

    response = AsyncMock()
    response.status = 500
    response.json = AsyncMock(return_value={"error": "x"})
    response.text = AsyncMock(return_value='{"error":"x"}')

    session = AsyncMock()
    session.__aenter__.return_value = session
    request_cm = MagicMock()
    request_cm.__aenter__ = AsyncMock(return_value=response)
    request_cm.__aexit__ = AsyncMock(return_value=False)
    session.request = MagicMock(return_value=request_cm)

    with patch("ha_simple_mcp.proxy.ClientSession", return_value=session):
        with pytest.raises(ProxyError):
            await proxy.call(endpoint, {"entity_id": "light.kitchen"})


@pytest.mark.asyncio
async def test_api_proxy_falls_back_to_text_payload() -> None:
    proxy = ApiProxy(
        McpSettings(
            bind_address="",
            port=0,
            auth_token="",
            target_user="owner",
            read_only=False,
            scope_allowlist=(),
            schema_cache_ttl=10,
            timeout=5,
            base_url="http://ha.local",
        )
    )
    endpoint = _endpoint_get()

    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(side_effect=ValueError("not json"))
    response.text = AsyncMock(return_value="plain text")

    session = AsyncMock()
    session.__aenter__.return_value = session
    request_cm = MagicMock()
    request_cm.__aenter__ = AsyncMock(return_value=response)
    request_cm.__aexit__ = AsyncMock(return_value=False)
    session.request = MagicMock(return_value=request_cm)

    with patch("ha_simple_mcp.proxy.ClientSession", return_value=session):
        status, body = await proxy.call(endpoint, {"entity_id": "light.kitchen"})

    assert status == 200
    assert body == "plain text"


@pytest.mark.asyncio
async def test_api_proxy_post_without_body_omits_json_argument() -> None:
    proxy = ApiProxy(
        McpSettings(
            bind_address="",
            port=0,
            auth_token="",
            target_user="owner",
            read_only=False,
            scope_allowlist=(),
            schema_cache_ttl=10,
            timeout=5,
            base_url="http://ha.local",
        )
    )
    endpoint = ApiEndpoint(
        method="POST",
        path="/api/services/{domain}/turn_on",
        description="Call service",
        returns_description="result",
        parameters=(
            ApiParameter(
                name="domain",
                required=True,
                description="Domain in path",
                schema_type="string",
                in_path=True,
            ),
        ),
        scope="ha.api.post.api.services.domain.turn_on",
    )

    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value={"ok": True})
    response.text = AsyncMock(return_value="ok")

    session = AsyncMock()
    session.__aenter__.return_value = session
    request_cm = MagicMock()
    request_cm.__aenter__ = AsyncMock(return_value=response)
    request_cm.__aexit__ = AsyncMock(return_value=False)
    session.request = MagicMock(return_value=request_cm)

    with patch("ha_simple_mcp.proxy.ClientSession", return_value=session):
        status, body = await proxy.call(endpoint, {"domain": "light"})

    assert status == 200
    assert body == {"ok": True}
    kwargs = session.request.call_args.kwargs
    assert kwargs["headers"] == {}
    assert "json" not in kwargs
    assert kwargs["timeout"] == 5


def test_build_request_skips_none_path_values() -> None:
    endpoint = _endpoint_get()
    path, body, query = build_request(endpoint, {"entity_id": None, "limit": 2})
    assert path == "/api/states/{entity_id}"
    assert body == {}
    assert query == {"limit": 2}


def test_build_request_ignores_none_path_value() -> None:
    endpoint = _endpoint_get()
    path, body, query = build_request(endpoint, {"entity_id": None, "limit": 1})

    assert path == "/api/states/{entity_id}"
    assert body == {}
    assert query == {"limit": 1}


def test_build_request_post_with_path_parameter() -> None:
    endpoint = ApiEndpoint(
        method="POST",
        path="/api/service/{domain}/turn_on",
        description="Call namespaced service",
        returns_description="result",
        parameters=(
            ApiParameter(
                name="domain",
                required=True,
                description="Domain in path",
                schema_type="string",
                in_path=True,
            ),
            ApiParameter(
                name="entity_id",
                required=True,
                description="Entity id in body",
                schema_type="string",
            ),
        ),
        scope="ha.api.post.api.service.domain.turn_on",
    )
    path, body, query = build_request(
        endpoint,
        {"domain": "light", "entity_id": "light.kitchen"},
    )
    assert path == "/api/service/light/turn_on"
    assert body == {"entity_id": "light.kitchen"}
    assert query == {}


def test_proxy_error_subclass_runtime_error() -> None:
    err = ProxyError("boom")
    assert isinstance(err, RuntimeError)
    assert str(err) == "boom"


def test_build_request_alias_points_to_public_function() -> None:
    from ha_simple_mcp.proxy import _build_request

    assert _build_request is build_request
