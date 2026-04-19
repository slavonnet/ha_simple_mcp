from custom_components.ha_simple_mcp.models import ApiEndpoint, ApiParameter
from custom_components.ha_simple_mcp.schema import SchemaCache, build_tools_schema


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
