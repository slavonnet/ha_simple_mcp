"""Consumer-side flow test: Client -> MCP -> mocked HA API."""

from __future__ import annotations

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer

import pytest

from custom_components.ha_simple_mcp.models import ApiEndpoint, ApiParameter, McpSettings
from custom_components.ha_simple_mcp.proxy import ApiProxy
from custom_components.ha_simple_mcp.schema import SchemaCache
from custom_components.ha_simple_mcp.server import McpHttpServer


class _Catalog:
    def __init__(self, endpoints):
        self._endpoints = endpoints

    async def discover(self):
        return self._endpoints

    async def get_by_tool_name(self, tool_name: str):
        for ep in self._endpoints:
            if ep.tool_name == tool_name:
                return ep
        return None


@pytest.mark.asyncio
async def test_end_to_end_client_to_ha_mock(aiohttp_unused_port):
    ha_api_app = web.Application()

    async def _states(request: web.Request):
        return web.json_response({"entity": request.match_info["entity_id"], "state": "on"})

    ha_api_app.router.add_get("/api/states/{entity_id}", _states)
    ha_server = TestServer(ha_api_app, port=aiohttp_unused_port())
    await ha_server.start_server()

    endpoint = ApiEndpoint(
        method="GET",
        path="/api/states/{entity_id}",
        description="Get state for entity",
        returns_description="Entity state payload",
        parameters=(
            ApiParameter(
                name="entity_id",
                required=True,
                description="Target entity id",
                schema_type="string",
                in_path=True,
            ),
        ),
        scope="ha.api.get.states",
    )
    settings = McpSettings(
        bind_address="127.0.0.1",
        port=aiohttp_unused_port(),
        auth_token="",
        target_user="owner",
        read_only=False,
        scope_allowlist=(),
        schema_cache_ttl=60,
        timeout=10,
    )
    proxy = ApiProxy(
        settings=McpSettings(
            bind_address=settings.bind_address,
            port=settings.port,
            auth_token=settings.auth_token,
            target_user=settings.target_user,
            read_only=settings.read_only,
            scope_allowlist=settings.scope_allowlist,
            schema_cache_ttl=settings.schema_cache_ttl,
            timeout=settings.timeout,
            base_url=f"http://127.0.0.1:{ha_server.port}",
        )
    )
    server = McpHttpServer(
        settings=settings,
        catalog=_Catalog([endpoint]),
        proxy=proxy,
        schema_cache=SchemaCache(ttl_seconds=60),
    )
    await server.start()

    base = f"http://127.0.0.1:{settings.port}"
    async with ClientSession() as session:
        tools_resp = await session.get(f"{base}/mcp/tools")
        assert tools_resp.status == 200
        tools_payload = await tools_resp.json()
        assert tools_payload["tools"][0]["name"] == endpoint.tool_name

        call_resp = await session.post(
            f"{base}/mcp/call",
            json={
                "tool": endpoint.tool_name,
                "arguments": {"entity_id": "light.kitchen"},
            },
        )
        assert call_resp.status == 200
        call_payload = await call_resp.json()
        assert call_payload["body"]["entity"] == "light.kitchen"
        assert call_payload["body"]["state"] == "on"

    await server.stop()
    await ha_server.close()
