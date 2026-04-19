"""Config flow for ha_simple_mcp."""

from __future__ import annotations

from collections.abc import Mapping
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
from .models import normalize_scope_list


def _normalize_scope(value: str) -> list[str]:
    """Normalize CSV scope into sorted unique list."""
    if not value.strip():
        return []
    chunks = [part.strip() for part in value.split(",")]
    return normalize_scope_list(chunks)


def _scope_csv_default(value: object) -> str:
    """Build CSV default string from stored allowlist value."""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(chunk) for chunk in value)
    return ""


def _build_entry_data(user_input: Mapping[str, Any], target_user: str) -> dict[str, object]:
    """Normalize user input payload into persisted config payload."""
    return {
        CONF_BIND_ADDRESS: str(user_input[CONF_BIND_ADDRESS]),
        CONF_PORT: int(user_input[CONF_PORT]),
        CONF_TOKEN: str(user_input[CONF_TOKEN]),
        CONF_TARGET_USER: target_user,
        CONF_READ_ONLY: bool(user_input[CONF_READ_ONLY]),
        CONF_TIMEOUT: int(user_input[CONF_TIMEOUT]),
        CONF_SCHEMA_CACHE_TTL: int(user_input[CONF_SCHEMA_CACHE_TTL]),
        CONF_SCOPE_ALLOWLIST: _normalize_scope(str(user_input[CONF_SCOPE_ALLOWLIST])),
    }


def _build_settings_schema(*, users: list[str], defaults: Mapping[str, Any]) -> vol.Schema:
    """Create shared settings schema for config and options flow."""
    default_user = str(defaults.get(CONF_TARGET_USER, users[0]))
    if default_user not in users:
        default_user = users[0]
    return vol.Schema(
        {
            vol.Optional(
                CONF_BIND_ADDRESS,
                default=str(defaults.get(CONF_BIND_ADDRESS, DEFAULT_BIND_ADDRESS)),
            ): str,
            vol.Optional(
                CONF_PORT,
                default=int(defaults.get(CONF_PORT, DEFAULT_PORT)),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Optional(CONF_TOKEN, default=str(defaults.get(CONF_TOKEN, ""))): str,
            vol.Required(CONF_TARGET_USER, default=default_user): vol.In(users),
            vol.Optional(
                CONF_READ_ONLY, default=bool(defaults.get(CONF_READ_ONLY, DEFAULT_READ_ONLY))
            ): bool,
            vol.Optional(
                CONF_SCOPE_ALLOWLIST,
                default=_scope_csv_default(defaults.get(CONF_SCOPE_ALLOWLIST, "")),
            ): str,
            vol.Optional(
                CONF_TIMEOUT,
                default=int(defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
            vol.Optional(
                CONF_SCHEMA_CACHE_TTL,
                default=int(defaults.get(CONF_SCHEMA_CACHE_TTL, DEFAULT_SCHEMA_CACHE_TTL)),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=86400)),
        }
    )


class HaSimpleMcpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Simple MCP."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return options flow handler for existing entry."""
        return HaSimpleMcpOptionsFlow(config_entry)

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
                entry_data = _build_entry_data(user_input, target_user)
                return self.async_create_entry(title="HA Simple MCP", data=entry_data)

        users = await _list_users(self.hass)
        if not users:
            users = ["owner"]

        schema = _build_settings_schema(users=users, defaults={})

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class HaSimpleMcpOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for live integration reconfiguration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Render and save options form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            target_user = user_input[CONF_TARGET_USER]
            if not await _user_exists(self.hass, target_user):
                errors["base"] = "user_not_found"
            else:
                return self.async_create_entry(
                    title="",
                    data=_build_entry_data(user_input, target_user),
                )

        users = await _list_users(self.hass)
        if not users:
            users = ["owner"]
        defaults = {**self._config_entry.data, **self._config_entry.options}
        schema = _build_settings_schema(users=users, defaults=defaults)
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)


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
