"""Constants for ha_simple_mcp integration."""

from __future__ import annotations

DOMAIN = "ha_simple_mcp"
PLATFORMS: list[str] = []

CONF_BIND_ADDRESS = "listen_host"
CONF_PORT = "listen_port"
CONF_TOKEN = "auth_token"
CONF_TARGET_USER = "ha_user"
CONF_READ_ONLY = "read_only"
CONF_SCOPE_ALLOWLIST = "allowed_scopes"
CONF_SCHEMA_CACHE_TTL = "schema_cache_ttl"
CONF_TIMEOUT = "timeout"

DEFAULT_BIND_ADDRESS = ""
DEFAULT_PORT = 8124
DEFAULT_READ_ONLY = False
DEFAULT_SCHEMA_CACHE_TTL = 300
DEFAULT_TIMEOUT = 15
