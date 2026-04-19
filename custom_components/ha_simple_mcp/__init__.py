"""Home Assistant entrypoint for HA Simple MCP integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:  # pragma: no cover - imported in real HA runtime
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
except ImportError:  # pragma: no cover - allows local tests without HA package
    ConfigEntry = Any  # type: ignore[misc,assignment]
    HomeAssistant = Any  # type: ignore[misc,assignment]

from .const import DOMAIN

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from .runtime import RuntimeData


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one config entry."""
    from .runtime import RuntimeData

    runtime = RuntimeData.from_entry(hass, entry)
    await runtime.start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one config entry."""
    domain_data: MutableMapping[str, RuntimeData] = hass.data[DOMAIN]
    runtime = domain_data.pop(entry.entry_id)
    await runtime.stop()
    if not domain_data:
        hass.data.pop(DOMAIN)
    return True
