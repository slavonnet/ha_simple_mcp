"""Tests for Home Assistant adapter layer under custom_components."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest


def _import_fresh(module_name: str) -> ModuleType:
    """Import module after removing previous instance from sys.modules."""
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _install_homeassistant_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install minimal homeassistant stubs required by adapter imports."""
    homeassistant_module: Any = ModuleType("homeassistant")
    config_entries_module: Any = ModuleType("homeassistant.config_entries")
    core_module: Any = ModuleType("homeassistant.core")

    class _StubConfigFlow:
        @classmethod
        def __init_subclass__(cls, **kwargs) -> None:
            return None

        async def async_set_unique_id(self, value: str) -> None:
            self.unique_id = value

        def _abort_if_unique_id_configured(self) -> None:
            self.abort_checked = True

        def async_create_entry(self, *, title: str, data: dict[str, object]) -> dict[str, object]:
            return {"type": "create_entry", "title": title, "data": data}

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema: object,
            errors: dict[str, str],
        ) -> dict[str, object]:
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors,
            }

    class _StubOptionsFlow:
        def async_create_entry(self, *, title: str, data: dict[str, object]) -> dict[str, object]:
            return {"type": "create_entry", "title": title, "data": data}

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema: object,
            errors: dict[str, str],
        ) -> dict[str, object]:
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors,
            }

    config_entries_module.ConfigFlow = _StubConfigFlow
    config_entries_module.ConfigEntry = object
    config_entries_module.OptionsFlow = _StubOptionsFlow
    core_module.HomeAssistant = object
    homeassistant_module.config_entries = config_entries_module
    homeassistant_module.core = core_module

    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant_module)
    monkeypatch.setitem(sys.modules, "homeassistant.config_entries", config_entries_module)
    monkeypatch.setitem(sys.modules, "homeassistant.core", core_module)


def _install_voluptuous_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install minimal voluptuous stub required by config flow tests."""
    module: Any = ModuleType("voluptuous")

    class _Schema:
        def __init__(self, schema: dict[object, object]) -> None:
            self.schema = schema

        def __call__(self, value: object) -> object:
            return value

    def _optional(key: str, default: object = None) -> tuple[str, str, object]:
        return ("optional", key, default)

    def _required(key: str, default: object = None) -> tuple[str, str, object]:
        return ("required", key, default)

    def _in(values: list[str]) -> tuple[str, tuple[str, ...]]:
        return ("in", tuple(values))

    def _all(*validators: object) -> tuple[str, tuple[object, ...]]:
        return ("all", validators)

    def _coerce(kind: type[object]) -> tuple[str, type[object]]:
        return ("coerce", kind)

    def _range(**kwargs: int | None) -> tuple[str, int | None, int | None]:
        return ("range", kwargs.get("min"), kwargs.get("max"))

    module.Schema = _Schema
    module.Optional = _optional
    module.Required = _required
    module.In = _in
    module.All = _all
    module.Coerce = _coerce
    module.Range = _range

    monkeypatch.setitem(sys.modules, "voluptuous", module)


def test_constants_contract() -> None:
    """Validate stable constants exported by integration."""
    from custom_components.ha_simple_mcp.const import (
        CONF_BIND_ADDRESS,
        CONF_PORT,
        CONF_READ_ONLY,
        DEFAULT_BIND_ADDRESS,
        DEFAULT_PORT,
        DEFAULT_READ_ONLY,
        DOMAIN,
        PLATFORMS,
    )

    assert DOMAIN == "ha_simple_mcp"
    assert PLATFORMS == []
    assert CONF_BIND_ADDRESS == "listen_host"
    assert CONF_PORT == "listen_port"
    assert CONF_READ_ONLY == "read_only"
    assert DEFAULT_BIND_ADDRESS == ""
    assert DEFAULT_PORT == 8124
    assert DEFAULT_READ_ONLY is False


def test_compatibility_reexports() -> None:
    """Ensure compatibility modules re-export expected package symbols."""
    from ha_api_mcp import (
        catalog as core_catalog,
    )
    from ha_api_mcp import (
        models as core_models,
    )
    from ha_api_mcp import (
        proxy as core_proxy,
    )
    from ha_api_mcp import (
        schema as core_schema,
    )
    from ha_api_mcp import (
        server as core_server,
    )
    from ha_api_mcp import (
        validation as core_validation,
    )

    from custom_components.ha_simple_mcp import (
        catalog as compat_catalog,
    )
    from custom_components.ha_simple_mcp import (
        models as compat_models,
    )
    from custom_components.ha_simple_mcp import (
        proxy as compat_proxy,
    )
    from custom_components.ha_simple_mcp import (
        schema as compat_schema,
    )
    from custom_components.ha_simple_mcp import (
        server as compat_server,
    )
    from custom_components.ha_simple_mcp import (
        validation as compat_validation,
    )

    assert compat_catalog.ApiCatalog is core_catalog.ApiCatalog
    assert compat_models.ApiEndpoint is core_models.ApiEndpoint
    assert compat_models.normalize_scope_list is core_models.normalize_scope_list
    assert compat_proxy.ApiProxy is core_proxy.ApiProxy
    assert compat_proxy.ProxyError is core_proxy.ProxyError
    assert compat_proxy._build_request is core_proxy.build_request
    assert compat_schema.SchemaCache is core_schema.SchemaCache
    assert issubclass(compat_server.McpHttpServer, core_server.McpHttpServer)
    assert compat_server.normalize_scopes is core_server.normalize_scopes
    assert compat_validation.ValidationError is core_validation.ValidationError
    assert compat_validation.matches_type is core_validation.matches_type
    assert compat_validation.validate_call is core_validation.validate_call


@pytest.mark.asyncio
async def test_adapter_server_compacts_tools_payload() -> None:
    """Ensure adapter server returns compact /mcp/tools metadata."""
    from aiohttp.test_utils import TestClient, TestServer
    from ha_api_mcp.models import ApiEndpoint, McpSettings
    from ha_api_mcp.schema import SchemaCache

    from custom_components.ha_simple_mcp.server import McpHttpServer

    class _Catalog:
        async def discover(self):
            return [
                ApiEndpoint(
                    method="POST",
                    path="/api/backup/upload",
                    description="Call Home Assistant endpoint POST /api/backup/upload via handle.",
                    returns_description="Raw Home Assistant JSON response.",
                    parameters=(),
                    scope="ha.api.post.api.backup.upload",
                ),
                ApiEndpoint(
                    method="GET",
                    path="/api/config",
                    description="Custom readable description",
                    returns_description="Config payload",
                    parameters=(),
                    scope="ha.api.get.api.config",
                ),
            ]

        async def get_by_tool_name(self, tool_name: str):
            return None

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
        catalog=_Catalog(),
        proxy=AsyncMock(),
        schema_cache=SchemaCache(ttl_seconds=60),
    )
    ts = TestServer(server.app)
    client = TestClient(ts)
    await client.start_server()
    try:
        resp = await client.get("/mcp/tools")
        assert resp.status == 200
        data = await resp.json()
    finally:
        await client.close()

    first = data["tools"][0]
    assert "x-ha-endpoint" not in first
    assert "description" not in first
    assert first["x-scope"] == "post.backup.upload"

    second = data["tools"][1]
    assert second["description"] == "Custom readable description"
    assert second["x-scope"] == "get.config"


@pytest.mark.asyncio
async def test_adapter_server_tools_unauthorized() -> None:
    """Ensure compact tools endpoint keeps auth behavior."""
    from aiohttp.test_utils import TestClient, TestServer
    from ha_api_mcp.models import McpSettings
    from ha_api_mcp.schema import SchemaCache

    from custom_components.ha_simple_mcp.server import McpHttpServer

    class _Catalog:
        async def discover(self):
            return []

        async def get_by_tool_name(self, tool_name: str):
            return None

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
        catalog=_Catalog(),
        proxy=AsyncMock(),
        schema_cache=SchemaCache(ttl_seconds=60),
    )
    ts = TestServer(server.app)
    client = TestClient(ts)
    await client.start_server()
    try:
        unauthorized = await client.get("/mcp/tools")
        assert unauthorized.status == 401
        assert await unauthorized.json() == {"error": "unauthorized"}
    finally:
        await client.close()


def test_adapter_scope_helpers_cover_branches() -> None:
    """Cover compact scope helpers for fallback and prefix paths."""
    from custom_components.ha_simple_mcp.server import (
        _compact_tool,
        _extract_compact_scope,
        _shorten_scope,
    )

    assert _extract_compact_scope({}) == ""
    assert _extract_compact_scope({"x-ha-endpoint": "bad"}) == ""
    assert _extract_compact_scope({"x-ha-endpoint": {"scope": None}}) == ""
    assert _extract_compact_scope(
        {"x-ha-endpoint": {"scope": "ha.api.post.api.backup.upload"}}
    ) == "post.backup.upload"
    assert _extract_compact_scope({"x-ha-endpoint": {"scope": "ha.api.get.config"}}) == "get.config"

    assert _shorten_scope("") == ""
    assert _shorten_scope("custom.scope") == "custom.scope"
    assert _shorten_scope("ha.api.get.api.states") == "get.states"

    compact = _compact_tool(
        {
            "name": "ha_get_root",
            "description": "Custom readable description",
            "inputSchema": {"type": "object"},
        }
    )
    assert "x-scope" not in compact


@pytest.mark.asyncio
async def test_runtime_data_builds_settings_and_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Build runtime from entry and verify start/stop delegation."""
    _install_homeassistant_stubs(monkeypatch)
    runtime_module = _import_fresh("custom_components.ha_simple_mcp.runtime")

    entry = SimpleNamespace(
        data={
            "listen_host": "127.0.0.1",
            "listen_port": 8124,
            "auth_token": "token",
            "ha_user": "owner",
            "read_only": True,
            "allowed_scopes": ["ha.api.get.*"],
            "schema_cache_ttl": 15,
            "timeout": 7,
        },
        options={},
    )
    hass = SimpleNamespace(
        http=SimpleNamespace(app=SimpleNamespace(router=SimpleNamespace(routes=lambda: []))),
        config=SimpleNamespace(api=SimpleNamespace(host="localhost", port=8123, use_ssl=False)),
    )

    runtime_data = runtime_module.RuntimeData.from_entry(hass, entry)
    assert runtime_data.mcp_server._settings.base_url == "http://localhost:8123"
    assert runtime_data.mcp_server._settings.port == 8124
    assert runtime_data.mcp_server._settings.read_only is True
    assert runtime_data.mcp_server._settings.scope_allowlist == ("ha.api.get.*",)

    entry_with_options = SimpleNamespace(
        data=entry.data,
        options={
            "listen_port": 8126,
            "read_only": False,
            "allowed_scopes": ["ha.api.post.*"],
        },
    )
    runtime_with_options = runtime_module.RuntimeData.from_entry(hass, entry_with_options)
    assert runtime_with_options.mcp_server._settings.port == 8126
    assert runtime_with_options.mcp_server._settings.read_only is False
    assert runtime_with_options.mcp_server._settings.scope_allowlist == ("ha.api.post.*",)
    ssl_hass = SimpleNamespace(
        config=SimpleNamespace(api=SimpleNamespace(host="ha", port=443, use_ssl=True))
    )
    assert runtime_module._resolve_base_url(ssl_hass) == "https://ha:443"

    start_mock = AsyncMock()
    stop_mock = AsyncMock()
    monkeypatch.setattr(runtime_data.mcp_server, "start", start_mock)
    monkeypatch.setattr(runtime_data.mcp_server, "stop", stop_mock)

    await runtime_data.start()
    await runtime_data.stop()
    start_mock.assert_awaited_once()
    stop_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_integration_entry_setup_and_unload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover integration entrypoint setup/unload paths."""
    module = _import_fresh("custom_components.ha_simple_mcp")

    runtime_object = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())
    runtime_module: Any = ModuleType("custom_components.ha_simple_mcp.runtime")

    class _RuntimeData:
        @classmethod
        def from_entry(cls, hass: object, entry: object) -> object:
            return runtime_object

    runtime_module.RuntimeData = _RuntimeData
    monkeypatch.setitem(sys.modules, "custom_components.ha_simple_mcp.runtime", runtime_module)

    hass = SimpleNamespace(data={})
    entry = SimpleNamespace(entry_id="entry-1")
    assert await module.async_setup_entry(hass, entry) is True
    assert hass.data["ha_simple_mcp"]["entry-1"] is runtime_object

    assert await module.async_unload_entry(hass, entry) is True
    runtime_object.start.assert_awaited_once()
    runtime_object.stop.assert_awaited_once()
    assert "ha_simple_mcp" not in hass.data


@pytest.mark.asyncio
async def test_integration_unload_keeps_other_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify unload preserves domain map when other entries exist."""
    module = _import_fresh("custom_components.ha_simple_mcp")

    runtime_object = SimpleNamespace(stop=AsyncMock())
    hass = SimpleNamespace(
        data={
            "ha_simple_mcp": {
                "entry-1": runtime_object,
                "entry-2": SimpleNamespace(stop=AsyncMock()),
            }
        }
    )
    entry = SimpleNamespace(entry_id="entry-1")

    assert await module.async_unload_entry(hass, entry) is True
    runtime_object.stop.assert_awaited_once()
    assert "ha_simple_mcp" in hass.data
    assert "entry-2" in hass.data["ha_simple_mcp"]


@pytest.mark.asyncio
async def test_config_flow_user_step_and_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover config flow form rendering, validation and entry creation."""
    _install_homeassistant_stubs(monkeypatch)
    _install_voluptuous_stub(monkeypatch)
    module = _import_fresh("custom_components.ha_simple_mcp.config_flow")

    inactive = SimpleNamespace(name="disabled", is_active=False)
    active_b = SimpleNamespace(name="beta", is_active=True)
    active_a = SimpleNamespace(name="alpha", is_active=True)
    auth = SimpleNamespace(async_get_users=AsyncMock(return_value=[inactive, active_b, active_a]))
    hass = SimpleNamespace(auth=auth)

    assert module._normalize_scope("  b, a, ,a ") == ["a", "b"]
    assert module._normalize_scope("   ") == []

    users = await module._list_users(hass)
    assert users == ["alpha", "beta"]
    assert await module._user_exists(hass, "alpha") is True
    assert await module._user_exists(hass, "missing") is False
    assert await module._list_users(SimpleNamespace(auth=None)) == []

    flow = module.HaSimpleMcpConfigFlow()
    flow.hass = hass

    form = await flow.async_step_user()
    assert form["type"] == "form"
    assert form["errors"] == {}
    target_user_key = next(
        key
        for key in form["data_schema"].schema
        if isinstance(key, tuple) and key[0] == "required" and key[1] == module.CONF_TARGET_USER
    )
    assert target_user_key[2] == "alpha"

    invalid = await flow.async_step_user(
        {
            module.CONF_BIND_ADDRESS: "",
            module.CONF_PORT: 8124,
            module.CONF_TOKEN: "",
            module.CONF_TARGET_USER: "missing",
            module.CONF_READ_ONLY: False,
            module.CONF_SCOPE_ALLOWLIST: "",
            module.CONF_TIMEOUT: 15,
            module.CONF_SCHEMA_CACHE_TTL: 300,
        }
    )
    assert invalid["type"] == "form"
    assert invalid["errors"]["base"] == "user_not_found"

    created = await flow.async_step_user(
        {
            module.CONF_BIND_ADDRESS: "0.0.0.0",
            module.CONF_PORT: 9000,
            module.CONF_TOKEN: "token",
            module.CONF_TARGET_USER: "alpha",
            module.CONF_READ_ONLY: True,
            module.CONF_SCOPE_ALLOWLIST: "ha.api.get.*, ha.api.get.* ,ha.api.post.*",
            module.CONF_TIMEOUT: 20,
            module.CONF_SCHEMA_CACHE_TTL: 600,
        }
    )
    assert created["type"] == "create_entry"
    assert created["title"] == "HA Simple MCP"
    assert created["data"][module.CONF_SCOPE_ALLOWLIST] == ["ha.api.get.*", "ha.api.post.*"]
    assert getattr(flow, "abort_checked", False) is True


@pytest.mark.asyncio
async def test_config_flow_fallback_owner_without_users(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover fallback default user when no Home Assistant users are available."""
    _install_homeassistant_stubs(monkeypatch)
    _install_voluptuous_stub(monkeypatch)
    module = _import_fresh("custom_components.ha_simple_mcp.config_flow")

    flow = module.HaSimpleMcpConfigFlow()
    flow.hass = SimpleNamespace(auth=SimpleNamespace(async_get_users=AsyncMock(return_value=[])))

    form = await flow.async_step_user()
    target_user_key = next(
        key
        for key in form["data_schema"].schema
        if isinstance(key, tuple) and key[0] == "required" and key[1] == module.CONF_TARGET_USER
    )
    assert target_user_key[2] == "owner"


@pytest.mark.asyncio
async def test_options_flow_uses_entry_defaults_and_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover options flow defaults and successful options save."""
    _install_homeassistant_stubs(monkeypatch)
    _install_voluptuous_stub(monkeypatch)
    module = _import_fresh("custom_components.ha_simple_mcp.config_flow")

    auth = SimpleNamespace(
        async_get_users=AsyncMock(return_value=[SimpleNamespace(name="owner", is_active=True)])
    )
    hass = SimpleNamespace(auth=auth)
    entry = SimpleNamespace(
        data={
            module.CONF_BIND_ADDRESS: "0.0.0.0",
            module.CONF_PORT: 8124,
            module.CONF_TOKEN: "",
            module.CONF_TARGET_USER: "owner",
            module.CONF_READ_ONLY: False,
            module.CONF_TIMEOUT: 15,
            module.CONF_SCHEMA_CACHE_TTL: 300,
            module.CONF_SCOPE_ALLOWLIST: ["ha.api.get.*"],
        },
        options={module.CONF_PORT: 9001},
    )
    flow = module.HaSimpleMcpOptionsFlow(entry)
    flow.hass = hass
    form = await flow.async_step_init()
    assert form["type"] == "form"
    assert form["errors"] == {}

    saved = await flow.async_step_init(
        {
            module.CONF_BIND_ADDRESS: "127.0.0.1",
            module.CONF_PORT: 8126,
            module.CONF_TOKEN: "next-token",
            module.CONF_TARGET_USER: "owner",
            module.CONF_READ_ONLY: True,
            module.CONF_SCOPE_ALLOWLIST: "ha.api.get.*,ha.api.post.*",
            module.CONF_TIMEOUT: 25,
            module.CONF_SCHEMA_CACHE_TTL: 1200,
        }
    )
    assert saved["data"][module.CONF_PORT] == 8126
    assert saved["data"][module.CONF_TOKEN] == "next-token"
    assert saved["data"][module.CONF_SCOPE_ALLOWLIST] == ["ha.api.get.*", "ha.api.post.*"]


@pytest.mark.asyncio
async def test_options_flow_rejects_unknown_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure options flow keeps form open when selected user is missing."""
    _install_homeassistant_stubs(monkeypatch)
    _install_voluptuous_stub(monkeypatch)
    module = _import_fresh("custom_components.ha_simple_mcp.config_flow")

    auth = SimpleNamespace(
        async_get_users=AsyncMock(return_value=[SimpleNamespace(name="owner", is_active=True)])
    )
    flow = module.HaSimpleMcpOptionsFlow(SimpleNamespace(data={}, options={}))
    flow.hass = SimpleNamespace(auth=auth)

    result = await flow.async_step_init(
        {
            module.CONF_BIND_ADDRESS: "",
            module.CONF_PORT: 8124,
            module.CONF_TOKEN: "",
            module.CONF_TARGET_USER: "missing",
            module.CONF_READ_ONLY: False,
            module.CONF_SCOPE_ALLOWLIST: "",
            module.CONF_TIMEOUT: 10,
            module.CONF_SCHEMA_CACHE_TTL: 120,
        }
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "user_not_found"


def test_config_flow_helper_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover helper branches used by config/options flow schema setup."""
    _install_homeassistant_stubs(monkeypatch)
    _install_voluptuous_stub(monkeypatch)
    module = _import_fresh("custom_components.ha_simple_mcp.config_flow")

    assert module._scope_csv_default(123) == ""
    schema = module._build_settings_schema(
        users=["owner"],
        defaults={module.CONF_TARGET_USER: "missing"},
    )
    target_user_key = next(
        key
        for key in schema.schema
        if isinstance(key, tuple) and key[0] == "required" and key[1] == module.CONF_TARGET_USER
    )
    assert target_user_key[2] == "owner"

    entry = SimpleNamespace(data={}, options={})
    options_flow = module.HaSimpleMcpConfigFlow.async_get_options_flow(entry)
    assert isinstance(options_flow, module.HaSimpleMcpOptionsFlow)


@pytest.mark.asyncio
async def test_options_flow_fallback_owner_without_users(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover options flow user fallback when auth has no active users."""
    _install_homeassistant_stubs(monkeypatch)
    _install_voluptuous_stub(monkeypatch)
    module = _import_fresh("custom_components.ha_simple_mcp.config_flow")

    flow = module.HaSimpleMcpOptionsFlow(SimpleNamespace(data={}, options={}))
    flow.hass = SimpleNamespace(auth=SimpleNamespace(async_get_users=AsyncMock(return_value=[])))

    form = await flow.async_step_init()
    target_user_key = next(
        key
        for key in form["data_schema"].schema
        if isinstance(key, tuple) and key[0] == "required" and key[1] == module.CONF_TARGET_USER
    )
    assert target_user_key[2] == "owner"
