"""Binary sensor of the Feuerwehr OÖ Einsätze integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import FwooeConfigEntry, FwooeCoordinator
from .entity import FwooeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FwooeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor."""
    async_add_entities([FwooeActiveIncidentSensor(entry.runtime_data)])


class FwooeActiveIncidentSensor(FwooeEntity, BinarySensorEntity):
    """On while at least one incident passes the filters."""

    _attr_translation_key = "active_incident"

    def __init__(self, coordinator: FwooeCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_active_incident"

    @property
    def is_on(self) -> bool:
        """Return true if there is a matching incident."""
        return self.coordinator.data.matching_count > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return how many incidents there are."""
        return {"count": self.coordinator.data.matching_count}
