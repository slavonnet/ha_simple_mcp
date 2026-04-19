from ha_api_mcp.models import (
    ApiEndpoint,
    ApiParameter,
    McpSettings,
    ToolCallResult,
    normalize_scope_list,
)


def test_normalize_scope_list_removes_empty_duplicates_and_whitespace() -> None:
    assert normalize_scope_list(["  ha.api.get.*  ", "", "ha.api.get.*", "x"]) == [
        "ha.api.get.*",
        "x",
    ]


def test_api_endpoint_tool_name_root_and_non_root() -> None:
    endpoint_root = ApiEndpoint(
        method="GET",
        path="/",
        description="root",
        returns_description="root",
    )
    endpoint_entity = ApiEndpoint(
        method="POST",
        path="/api/states/{entity_id}",
        description="state",
        returns_description="state",
    )

    assert endpoint_root.tool_name == "ha_get_root"
    assert endpoint_entity.tool_name == "ha_post_api_states_entity_id"


def test_api_endpoint_scope_allowlist_matching() -> None:
    endpoint = ApiEndpoint(
        method="GET",
        path="/api/states",
        description="state",
        returns_description="state",
        scope="ha.api.get.api.states",
    )

    assert endpoint.allow_for_scope((), ())
    assert endpoint.allow_for_scope(("ha.api.get.*",), ())
    assert not endpoint.allow_for_scope(("ha.api.post.*",), ())
    assert endpoint.allow_for_scope(("ha.api.get.*",), ("ha.api.get.api.*",))
    assert not endpoint.allow_for_scope(("ha.api.get.*",), ("ha.api.post.*",))


def test_dataclass_defaults_and_result_model() -> None:
    settings = McpSettings(
        bind_address="",
        port=8124,
        auth_token="",
        target_user="owner",
        read_only=False,
        scope_allowlist=(),
        schema_cache_ttl=300,
        timeout=15,
    )
    result = ToolCallResult(status=200, body={"ok": True})
    param = ApiParameter(name="x", required=True, description="desc")

    assert settings.base_url == ""
    assert result.status == 200
    assert result.body == {"ok": True}
    assert param.schema_type == "string"
    assert param.in_path is False
