from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from custom_components.ha_simple_mcp.models import ApiEndpoint, ApiParameter, McpSettings
from custom_components.ha_simple_mcp.schema import SchemaCache, build_tools_schema
from custom_components.ha_simple_mcp.server import McpHttpServer


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
    )
    server = McpHttpServer(
        settings=settings, catalog=catalog, proxy=proxy, schema_cache=cache
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
    )
    server = McpHttpServer(
        settings=settings, catalog=catalog, proxy=proxy, schema_cache=cache
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
    finally:
        await client.close()
