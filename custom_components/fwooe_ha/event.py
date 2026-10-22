"""Event entity of the Feuerwehr OÖ Einsätze integration.

Fires when an incident that passes the filters appears and when its alarm level goes up,
which is what an automation (a notification, a light) wants to trigger on.
"""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import EVENT_ALARM_RAISED, EVENT_NEW_INCIDENT, EVENT_TYPES
from .coordinator import FwooeConfigEntry, FwooeCoordinator
from .entity import FwooeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FwooeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the event entity."""
    async_add_entities([FwooeIncidentEvent(entry.runtime_data)])


class FwooeIncidentEvent(FwooeEntity, EventEntity):
    """Announces new and escalated incidents; the event data is the incident."""

    _attr_translation_key = "incident"
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: FwooeCoordinator) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_incident_event"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fire an event for every new or escalated incident of this update."""
        data = self.coordinator.data
        for incident in data.new:
            self._trigger_event(EVENT_NEW_INCIDENT, incident.as_dict())
        for incident in data.raised:
            self._trigger_event(EVENT_ALARM_RAISED, incident.as_dict())
        self.async_write_ha_state()
