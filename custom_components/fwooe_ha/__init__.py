"""The Feuerwehr OÖ Einsätze integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import FwooeClient
from .card import async_register_card
from .const import DOMAIN
from .coordinator import FwooeConfigEntry, FwooeCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.GEO_LOCATION,
    Platform.SENSOR,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration: make the dashboard card available (once, for all feeds)."""
    await async_register_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FwooeConfigEntry) -> bool:
    """Set up a feed from a config entry."""
    coordinator = FwooeCoordinator(hass, entry, FwooeClient(async_get_clientsession(hass)))
    # Raises ConfigEntryNotReady when the feed cannot be read; Home Assistant retries.
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Changed filters or interval: reload, so the coordinator is rebuilt with them.
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: FwooeConfigEntry) -> None:
    """Reload the entry after its options changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FwooeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
