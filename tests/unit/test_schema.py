from ha_api_mcp.models import ApiEndpoint, ApiParameter
from ha_api_mcp.schema import SchemaCache, build_tools_schema


def test_build_tools_schema_contains_required_metadata() -> None:
    endpoint = ApiEndpoint(
        method="GET",
        path="/api/states/{entity_id}",
        description="Read state",
        returns_description="State payload",
        parameters=(
            ApiParameter("entity_id", True, "Entity identifier", "string", True),
            ApiParameter("expand", False, "Expand attrs", "boolean", False),
        ),
        scope="ha.api.get.api.states.entity_id",
    )

    tools = build_tools_schema([endpoint])
    assert len(tools) == 1
    tool = tools[0]
    assert tool["name"] == "ha_get_api_states_entity_id"
    assert tool["inputSchema"]["required"] == ["entity_id"]
    assert tool["inputSchema"]["properties"]["expand"]["type"] == "boolean"
    assert tool["returns"]["description"] == "State payload"
    assert tool["x-ha-endpoint"]["scope"] == endpoint.scope


def test_schema_cache_ttl_invalidation() -> None:
    cache = SchemaCache(ttl_seconds=0)
    cache.set([{"name": "x"}])
    assert cache.get() is None


def test_schema_cache_get_empty_and_repopulate() -> None:
    cache = SchemaCache(ttl_seconds=60)
    assert cache.get() is None
    cache.set([{"name": "n"}])
    assert cache.get() == [{"name": "n"}]


def test_build_tools_schema_root_path_name() -> None:
    endpoint = ApiEndpoint(
        method="GET",
        path="/",
        description="Root endpoint",
        returns_description="root payload",
        parameters=(),
        scope="ha.api.get.root",
    )
    tool = build_tools_schema([endpoint])[0]
    assert tool["name"] == "ha_get_root"


def test_schema_cache_get_or_build_and_invalidate() -> None:
    cache = SchemaCache(ttl_seconds=60)

    async def _fetch():
        return [
            ApiEndpoint(
                method="GET",
                path="/api/config",
                description="Get config",
                returns_description="Config payload",
                parameters=(),
                scope="ha.api.get.api.config",
            )
        ]

    import asyncio

    tools = asyncio.run(cache.get_or_build(_fetch))
    assert tools[0]["name"] == "ha_get_api_config"

    cached = cache.get()
    assert cached is not None
    assert cached[0]["name"] == "ha_get_api_config"

    cache.invalidate()
    assert cache.get() is None


def test_schema_cache_get_or_build_uses_cached_value() -> None:
    cache = SchemaCache(ttl_seconds=60)
    cache.set([{"name": "cached"}])

    async def _fetch():
        raise AssertionError("fetch should not be called when cache exists")

    import asyncio

    tools = asyncio.run(cache.get_or_build(_fetch))
    assert tools == [{"name": "cached"}]
