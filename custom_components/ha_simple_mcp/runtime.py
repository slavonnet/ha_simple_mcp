"""Runtime wiring for HA Simple MCP."""

from __future__ import annotations

from dataclasses import dataclass

from ha_api_mcp.catalog import ApiCatalog
from ha_api_mcp.models import McpSettings
from ha_api_mcp.proxy import ApiProxy
from ha_api_mcp.schema import SchemaCache
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BIND_ADDRESS,
    CONF_PORT,
    CONF_READ_ONLY,
    CONF_SCHEMA_CACHE_TTL,
    CONF_SCOPE_ALLOWLIST,
    CONF_TARGET_USER,
    CONF_TIMEOUT,
    CONF_TOKEN,
    DEFAULT_BIND_ADDRESS,
    DEFAULT_PORT,
    DEFAULT_READ_ONLY,
    DEFAULT_SCHEMA_CACHE_TTL,
    DEFAULT_TIMEOUT,
)
from .server import McpHttpServer


@dataclass(slots=True)
class RuntimeData:
    """Holds runtime objects for one config entry."""

    hass: HomeAssistant
    entry: ConfigEntry
    mcp_server: McpHttpServer

    @classmethod
    def from_entry(cls, hass: HomeAssistant, entry: ConfigEntry) -> RuntimeData:
        """Create runtime data from config entry."""
        data = {**entry.data, **entry.options}
        base_url = _resolve_base_url(hass)
        settings = McpSettings(
            bind_address=str(data.get(CONF_BIND_ADDRESS, DEFAULT_BIND_ADDRESS)),
            port=int(data.get(CONF_PORT, DEFAULT_PORT)),
            auth_token=str(data.get(CONF_TOKEN, "")),
            target_user=str(data.get(CONF_TARGET_USER, "")),
            read_only=bool(data.get(CONF_READ_ONLY, DEFAULT_READ_ONLY)),
            scope_allowlist=tuple(data.get(CONF_SCOPE_ALLOWLIST, [])),
            schema_cache_ttl=int(data.get(CONF_SCHEMA_CACHE_TTL, DEFAULT_SCHEMA_CACHE_TTL)),
            timeout=int(data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            base_url=base_url,
        )
        catalog = ApiCatalog(hass)
        proxy = ApiProxy(settings=settings)
        cache = SchemaCache(ttl_seconds=settings.schema_cache_ttl)
        mcp_server = McpHttpServer(
            settings=settings,
            catalog=catalog,
            proxy=proxy,
            schema_cache=cache,
        )
        return cls(hass=hass, entry=entry, mcp_server=mcp_server)

    async def start(self) -> None:
        """Start runtime."""
        await self.mcp_server.start()

    async def stop(self) -> None:
        """Stop runtime."""
        await self.mcp_server.stop()


def _resolve_base_url(hass: HomeAssistant) -> str:
    """Resolve HA API base URL from runtime config."""
    api_cfg = hass.config.api
    scheme = "https" if getattr(api_cfg, "use_ssl", False) else "http"
    return f"{scheme}://{api_cfg.host}:{api_cfg.port}"
