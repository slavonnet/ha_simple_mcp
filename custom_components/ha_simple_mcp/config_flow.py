"""Config flow for ha_simple_mcp."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
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
    DOMAIN,
)


def _normalize_scope(value: str) -> list[str]:
    """Normalize CSV scope into sorted unique list."""
    if not value.strip():
        return []
    chunks = [part.strip() for part in value.split(",")]
    return sorted({part for part in chunks if part})


class HaSimpleMcpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Simple MCP."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id("singleton")
            self._abort_if_unique_id_configured()

            target_user = user_input[CONF_TARGET_USER]
            if not await _user_exists(self.hass, target_user):
                errors["base"] = "user_not_found"
            else:
                entry_data = {
                    CONF_BIND_ADDRESS: user_input[CONF_BIND_ADDRESS],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_TOKEN: user_input[CONF_TOKEN],
                    CONF_TARGET_USER: target_user,
                    CONF_READ_ONLY: user_input[CONF_READ_ONLY],
                    CONF_TIMEOUT: user_input[CONF_TIMEOUT],
                    CONF_SCHEMA_CACHE_TTL: user_input[CONF_SCHEMA_CACHE_TTL],
                    CONF_SCOPE_ALLOWLIST: _normalize_scope(
                        user_input[CONF_SCOPE_ALLOWLIST]
                    ),
                }
                return self.async_create_entry(title="HA Simple MCP", data=entry_data)

        users = await _list_users(self.hass)
        if not users:
            users = ["owner"]

        schema = vol.Schema(
            {
                vol.Optional(CONF_BIND_ADDRESS, default=DEFAULT_BIND_ADDRESS): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_TOKEN, default=""): str,
                vol.Required(CONF_TARGET_USER, default=users[0]): vol.In(users),
                vol.Optional(CONF_READ_ONLY, default=DEFAULT_READ_ONLY): bool,
                vol.Optional(CONF_SCOPE_ALLOWLIST, default=""): str,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=120)
                ),
                vol.Optional(
                    CONF_SCHEMA_CACHE_TTL, default=DEFAULT_SCHEMA_CACHE_TTL
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=86400)),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


async def _list_users(hass: HomeAssistant) -> list[str]:
    """List available user names."""
    auth = hass.auth
    if auth is None:
        return []
    users = await auth.async_get_users()
    return sorted({user.name for user in users if user.is_active})


async def _user_exists(hass: HomeAssistant, user_name: str) -> bool:
    """Check that a user with selected name exists and active."""
    users = await _list_users(hass)
    return user_name in users
