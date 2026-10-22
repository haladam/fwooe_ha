"""Geo location entities: one per running incident, so they show up on the map."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import location as location_util

from .const import DOMAIN
from .coordinator import FwooeConfigEntry, FwooeCoordinator
from .entity import FwooeEntity
from .models import Incident

SOURCE = DOMAIN


def _has_position(incident: Incident) -> bool:
    return incident.latitude is not None and incident.longitude is not None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FwooeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entity for every incident, now and whenever one appears."""
    coordinator = entry.runtime_data
    tracked: set[str] = set()

    # Entities of incidents that ended while Home Assistant was not running would stay
    # behind as unavailable registry entries: drop them.
    registry = er.async_get(hass)
    wanted = {
        f"{entry.entry_id}_{incident.id}"
        for incident in coordinator.data.incidents
        if _has_position(incident)
    }
    for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
        if registered.domain == "geo_location" and registered.unique_id not in wanted:
            registry.async_remove(registered.entity_id)

    @callback
    def _add_new_incidents() -> None:
        new_entities = []
        for incident in coordinator.data.incidents:
            if incident.id in tracked or not _has_position(incident):
                continue
            tracked.add(incident.id)
            new_entities.append(FwooeGeoLocation(coordinator, incident, tracked.discard))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_incidents()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_incidents))


class FwooeGeoLocation(FwooeEntity, GeolocationEvent):
    """A running incident at its position; the state is the distance to home in km.

    The entity removes itself when the incident is no longer in the (filtered) feed.
    """

    # The entity name is the incident; like every entity of a device it is shown as
    # "<device name> <incident>", which tells apart several feeds.
    _attr_source = SOURCE
    _attr_unit_of_measurement = UnitOfLength.KILOMETERS
    _unrecorded_attributes = frozenset({"units"})

    def __init__(
        self,
        coordinator: FwooeCoordinator,
        incident: Incident,
        forget: Callable[[str], None],
    ) -> None:
        """Initialize the entity from an incident."""
        super().__init__(coordinator)
        self._incident_id = incident.id
        self._forget = forget
        self._discarding = False
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{incident.id}"
        self._apply(incident)

    def _apply(self, incident: Incident) -> None:
        """Take over the current data of the incident."""
        self._incident = incident
        self._attr_name = (
            f"{incident.description} ({incident.location})"
            if incident.location
            else incident.description
        )
        self._attr_latitude = incident.latitude
        self._attr_longitude = incident.longitude
        home = self.coordinator.hass.config
        meters = location_util.distance(
            home.latitude, home.longitude, incident.latitude, incident.longitude
        )
        self._attr_distance = round(meters / 1000, 1) if meters is not None else None
        if incident.kind.upper() == "BRAND":
            self._attr_icon = "mdi:fire"
        elif incident.self_initiated:
            self._attr_icon = "mdi:fire-truck"
        else:
            self._attr_icon = "mdi:alarm-light"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the details of the incident (the position is part of the state)."""
        details = self._incident.as_dict()
        del details["latitude"], details["longitude"]
        return details

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh from the new data, or go away when the incident has ended."""
        incident = next(
            (
                candidate
                for candidate in self.coordinator.data.incidents
                if candidate.id == self._incident_id and _has_position(candidate)
            ),
            None,
        )
        if incident is None:
            if not self._discarding:
                self._discarding = True
                self.hass.async_create_task(self._async_discard())
            return
        self._apply(incident)
        self.async_write_ha_state()

    async def _async_discard(self) -> None:
        """Remove the entity, and its registry entry: incidents never come back."""
        registry = er.async_get(self.hass)
        if registry.async_get(self.entity_id) is not None:
            # The registry tells the entity to remove itself (and its state).
            registry.async_remove(self.entity_id)
        else:
            await self.async_remove(force_remove=True)

    async def async_will_remove_from_hass(self) -> None:
        """Let the platform know the incident is no longer tracked."""
        self._forget(self._incident_id)
