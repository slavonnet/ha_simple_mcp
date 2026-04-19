from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ha_simple_mcp.models import ApiEndpoint, ApiParameter, McpSettings
from ha_simple_mcp.proxy import ProxyError
from ha_simple_mcp.schema import SchemaCache, build_tools_schema
from ha_simple_mcp.server import McpHttpServer, normalize_scopes


class _Catalog:
    def __init__(self, endpoints):
        self._endpoints = endpoints

    async def discover(self):
        return self._endpoints

    async def get_by_tool_name(self, tool_name: str):
        for endpoint in self._endpoints:
            if endpoint.tool_name == tool_name:
                return endpoint
        return None


class _EmptyCatalog:
    async def discover(self):
        return []

    async def get_by_tool_name(self, tool_name: str):
        return None


class _UnauthorizedServer(McpHttpServer):
    @staticmethod
    def _authorized(request):
        return False


class _NoSiteServer(McpHttpServer):
    async def stop(self) -> None:
        self._site = None
        await super().stop()


def test_normalize_scopes_filters_invalid_values() -> None:
    assert normalize_scopes(["a", "", 1, "b"]) == ("a", "b")
    assert normalize_scopes("ha.api.*") == ()


@pytest.mark.asyncio
async def test_tools_requires_auth_token() -> None:
    endpoint = ApiEndpoint(
        method="GET",
        path="/api/states",
        description="desc",
        returns_description="json",
        parameters=(),
        scope="ha.api.get.states",
    )
    catalog = _Catalog([endpoint])
    cache = SchemaCache(ttl_seconds=60)
    proxy = AsyncMock()
    settings = McpSettings(
        bind_address="",
        port=0,
        auth_token="secret",
        target_user="owner",
        read_only=False,
        scope_allowlist=(),
        schema_cache_ttl=60,
        timeout=10,
        base_url="http://ha.local:8123",
    )
    server = McpHttpServer(
        settings=settings,
        catalog=catalog,  # type: ignore[arg-type]
        proxy=proxy,
        schema_cache=cache,
    )
    ts = TestServer(server.app)
    client = TestClient(ts)
    await client.start_server()
    try:
        resp = await client.get("/mcp/tools")
        assert resp.status == 401

        resp = await client.get("/mcp/tools", headers={"Authorization": "Bearer secret"})
        assert resp.status == 200
        data = await resp.json()
        assert data["tools"][0]["name"] == build_tools_schema([endpoint])[0]["name"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_call_respects_scope_and_validation() -> None:
    endpoint = ApiEndpoint(
        method="GET",
        path="/api/states/{entity_id}",
        description="desc",
        returns_description="json",
        parameters=(
            ApiParameter("entity_id", True, "id", "string"),
        ),
        scope="ha.api.get.states.entity",
    )
    catalog = _Catalog([endpoint])
    cache = SchemaCache(ttl_seconds=60)
    proxy = AsyncMock()
    proxy.call.return_value = (200, {"ok": True})
    settings = McpSettings(
        bind_address="",
        port=0,
        auth_token="",
        target_user="owner",
        read_only=False,
        scope_allowlist=("ha.api.get.states.entity",),
        schema_cache_ttl=60,
        timeout=10,
        base_url="http://ha.local:8123",
    )
    server = McpHttpServer(
        settings=settings,
        catalog=catalog,  # type: ignore[arg-type]
        proxy=proxy,
        schema_cache=cache,
    )
    ts = TestServer(server.app)
    client = TestClient(ts)
    await client.start_server()
    try:
        ok = await client.post(
            "/mcp/call",
            json={"tool": endpoint.tool_name, "arguments": {"entity_id": "sensor.temp"}},
        )
        assert ok.status == 200
        body = await ok.json()
        assert body["status"] == 200

        bad = await client.post(
            "/mcp/call",
            json={"tool": endpoint.tool_name, "arguments": {}},
        )
        assert bad.status == 400

        blocked = await client.post(
            "/mcp/call",
            json={
                "tool": endpoint.tool_name,
                "arguments": {"entity_id": "sensor.temp"},
                "scopes": ["ha.api.get.other.*"],
            },
        )
        assert blocked.status == 403

        invalid = await client.post(
            "/mcp/call",
            data="{bad-json",
            headers={"Content-Type": "application/json"},
        )
        assert invalid.status == 400

        missing = await client.post("/mcp/call", json={"tool": endpoint.tool_name})
        assert missing.status == 400

        unknown = await client.post(
            "/mcp/call",
            json={"tool": "ha_get_unknown", "arguments": {}},
        )
        assert unknown.status == 404
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_proxy_error_is_translated_to_http_502() -> None:
    endpoint = ApiEndpoint(
        method="GET",
        path="/api/states/{entity_id}",
        description="desc",
        returns_description="json",
        parameters=(ApiParameter("entity_id", True, "id", "string"),),
        scope="ha.api.get.states.entity",
    )
    catalog = _Catalog([endpoint])
    cache = SchemaCache(ttl_seconds=60)
    proxy = AsyncMock()
    proxy.call.side_effect = ProxyError("boom")
    settings = McpSettings(
        bind_address="",
        port=0,
        auth_token="",
        target_user="owner",
        read_only=False,
        scope_allowlist=(),
        schema_cache_ttl=60,
        timeout=10,
        base_url="http://ha.local:8123",
    )
    server = McpHttpServer(
        settings=settings,
        catalog=catalog,  # type: ignore[arg-type]
        proxy=proxy,
        schema_cache=cache,
    )
    ts = TestServer(server.app)
    client = TestClient(ts)
    await client.start_server()
    try:
        resp = await client.post(
            "/mcp/call",
            json={"tool": endpoint.tool_name, "arguments": {"entity_id": "sensor.temp"}},
        )
        assert resp.status == 502
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_call_handles_unknown_tool_and_invalid_payload() -> None:
    endpoint = ApiEndpoint(
        method="GET",
        path="/api/states/{entity_id}",
        description="desc",
        returns_description="json",
        parameters=(ApiParameter("entity_id", True, "id", "string"),),
        scope="ha.api.get.states.entity",
    )
    catalog = _Catalog([endpoint])
    cache = SchemaCache(ttl_seconds=60)
    proxy = AsyncMock()
    settings = McpSettings(
        bind_address="",
        port=0,
        auth_token="",
        target_user="owner",
        read_only=False,
        scope_allowlist=("ha.api.get.states.entity",),
        schema_cache_ttl=60,
        timeout=10,
        base_url="http://ha.local:8123",
    )
    server = McpHttpServer(
        settings=settings,
        catalog=catalog,  # type: ignore[arg-type]
        proxy=proxy,
        schema_cache=cache,
    )
    ts = TestServer(server.app)
    client = TestClient(ts)
    await client.start_server()
    try:
        unknown = await client.post(
            "/mcp/call",
            json={"tool": "ha_get_api_unknown", "arguments": {}},
        )
        assert unknown.status == 404

        missing = await client.post("/mcp/call", json={"foo": "bar"})
        assert missing.status == 400
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_call_readonly_and_proxy_error_paths() -> None:
    endpoint = ApiEndpoint(
        method="POST",
        path="/api/services/light/turn_on",
        description="turn on",
        returns_description="json",
        parameters=(ApiParameter("entity_id", True, "id", "string"),),
        scope="ha.api.post.services.light.turn_on",
    )
    catalog = _Catalog([endpoint])
    cache = SchemaCache(ttl_seconds=60)
    proxy = AsyncMock()
    proxy.call.side_effect = RuntimeError("boom")
    settings = McpSettings(
        bind_address="",
        port=0,
        auth_token="",
        target_user="owner",
        read_only=True,
        scope_allowlist=(),
        schema_cache_ttl=60,
        timeout=10,
        base_url="http://ha.local:8123",
    )
    server = McpHttpServer(
        settings=settings,
        catalog=catalog,  # type: ignore[arg-type]
        proxy=proxy,
        schema_cache=cache,
    )
    ts = TestServer(server.app)
    client = TestClient(ts)
    await client.start_server()
    try:
        readonly = await client.post(
            "/mcp/call",
            json={"tool": endpoint.tool_name, "arguments": {"entity_id": "light.kitchen"}},
        )
        assert readonly.status == 403
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_call_handles_bad_json_unknown_tool_and_proxy_error() -> None:
    endpoint = ApiEndpoint(
        method="GET",
        path="/api/states",
        description="desc",
        returns_description="json",
        parameters=(),
        scope="ha.api.get.states",
    )
    catalog = _Catalog([endpoint])
    cache = SchemaCache(ttl_seconds=60)
    proxy = AsyncMock()
    proxy.call.side_effect = RuntimeError("boom")
    settings = McpSettings(
        bind_address="",
        port=0,
        auth_token="",
        target_user="owner",
        read_only=False,
        scope_allowlist=(),
        schema_cache_ttl=60,
        timeout=10,
        base_url="http://ha.local:8123",
    )
    server = McpHttpServer(
        settings=settings,
        catalog=catalog,  # type: ignore[arg-type]
        proxy=proxy,
        schema_cache=cache,
    )
    ts = TestServer(server.app)
    client = TestClient(ts)
    await client.start_server()
    try:
        invalid = await client.post(
            "/mcp/call",
            data="{bad-json",
            headers={"Content-Type": "application/json"},
        )
        assert invalid.status == 400

        unknown = await client.post(
            "/mcp/call",
            json={"tool": "ha_get_unknown", "arguments": {}},
        )
        assert unknown.status == 404
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_tools_unauthorized_and_unknown_tool_paths() -> None:
    cache = SchemaCache(ttl_seconds=60)
    proxy = AsyncMock()
    settings = McpSettings(
        bind_address="",
        port=0,
        auth_token="token",
        target_user="owner",
        read_only=False,
        scope_allowlist=(),
        schema_cache_ttl=60,
        timeout=10,
        base_url="http://ha.local:8123",
    )
    server = McpHttpServer(
        settings=settings,
        catalog=_EmptyCatalog(),  # type: ignore[arg-type]
        proxy=proxy,
        schema_cache=cache,
    )
    ts = TestServer(server.app)
    client = TestClient(ts)
    await client.start_server()
    try:
        tools = await client.get("/mcp/tools")
        assert tools.status == 401

        unknown = await client.post(
            "/mcp/call",
            headers={"Authorization": "Bearer token"},
            json={"tool": "ha_get_unknown", "arguments": {}},
        )
        assert unknown.status == 404
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_health_endpoint_requires_auth_when_token_set() -> None:
    cache = SchemaCache(ttl_seconds=60)
    proxy = AsyncMock()
    settings = McpSettings(
        bind_address="",
        port=0,
        auth_token="token",
        target_user="owner",
        read_only=False,
        scope_allowlist=(),
        schema_cache_ttl=60,
        timeout=10,
        base_url="http://ha.local:8123",
    )
    server = McpHttpServer(
        settings=settings,
        catalog=_EmptyCatalog(),  # type: ignore[arg-type]
        proxy=proxy,
        schema_cache=cache,
    )
    ts = TestServer(server.app)
    client = TestClient(ts)
    await client.start_server()
    try:
        unauthorized = await client.get("/health")
        assert unauthorized.status == 401

        authorized = await client.get("/health", headers={"Authorization": "Bearer token"})
        assert authorized.status == 200
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_tools_and_health_unauthorized_branch_forced() -> None:
    cache = SchemaCache(ttl_seconds=60)
    proxy = AsyncMock()
    settings = McpSettings(
        bind_address="",
        port=0,
        auth_token="",
        target_user="owner",
        read_only=False,
        scope_allowlist=(),
        schema_cache_ttl=60,
        timeout=10,
        base_url="http://ha.local:8123",
    )
    server = _UnauthorizedServer(
        settings=settings,
        catalog=_EmptyCatalog(),  # type: ignore[arg-type]
        proxy=proxy,
        schema_cache=cache,
    )
    ts = TestServer(server.app)
    client = TestClient(ts)
    await client.start_server()
    try:
        health = await client.get("/health")
        assert health.status == 401

        tools = await client.get("/mcp/tools")
        assert tools.status == 401
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_call_unauthorized_branch_forced() -> None:
    cache = SchemaCache(ttl_seconds=60)
    proxy = AsyncMock()
    settings = McpSettings(
        bind_address="",
        port=0,
        auth_token="",
        target_user="owner",
        read_only=False,
        scope_allowlist=(),
        schema_cache_ttl=60,
        timeout=10,
        base_url="http://ha.local:8123",
    )
    server = _UnauthorizedServer(
        settings=settings,
        catalog=_EmptyCatalog(),  # type: ignore[arg-type]
        proxy=proxy,
        schema_cache=cache,
    )
    ts = TestServer(server.app)
    client = TestClient(ts)
    await client.start_server()
    try:
        call = await client.post(
            "/mcp/call",
            json={"tool": "ha_get_unknown", "arguments": {}},
        )
        assert call.status == 401
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_stop_handles_absent_site() -> None:
    cache = SchemaCache(ttl_seconds=60)
    proxy = AsyncMock()
    settings = McpSettings(
        bind_address="",
        port=0,
        auth_token="",
        target_user="owner",
        read_only=False,
        scope_allowlist=(),
        schema_cache_ttl=60,
        timeout=10,
        base_url="http://ha.local:8123",
    )
    server = _NoSiteServer(
        settings=settings,
        catalog=_EmptyCatalog(),  # type: ignore[arg-type]
        proxy=proxy,
        schema_cache=cache,
    )
    await server.start()
    await server.stop()


def test_catalog_like_base_raises_not_implemented() -> None:
    from ha_simple_mcp.server import _CatalogLike

    catalog = _CatalogLike()
    with pytest.raises(NotImplementedError):
        catalog.discover()
    with pytest.raises(NotImplementedError):
        catalog.get_by_tool_name("ha_get_states")
