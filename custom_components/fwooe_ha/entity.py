"""Base entity of the Feuerwehr OÖ Einsätze integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONFIGURATION_URL, DOMAIN, MANUFACTURER
from .coordinator import FwooeCoordinator


class FwooeEntity(CoordinatorEntity[FwooeCoordinator]):
    """An entity of a feed: all of them share one service device."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: FwooeCoordinator) -> None:
        """Initialize the entity and attach it to the device of the config entry."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model="Einsatzübersicht",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=CONFIGURATION_URL,
        )
