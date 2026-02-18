"""Sensor platform for Upper Austria Fire Brigade."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OOELFVDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Upper Austria Fire Brigade sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        OOELFVIncidentSensor(coordinator, entry),
        OOELFVCountSensor(coordinator, entry),
    ]
    
    async_add_entities(entities)


class OOELFVIncidentSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing current fire brigade incidents."""

    _attr_icon = "mdi:fire-truck"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OOELFVDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "Incidents"
        self._attr_unique_id = f"{entry.entry_id}_incidents"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data["name"],
            "manufacturer": "OÖ Landes-Feuerwehrverband",
            "model": "Fire Brigade Incidents",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> int:
        """Return the number of active incidents."""
        if not self.coordinator.data:
            return 0
        return self.coordinator.data.get("filtered_count", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}
        
        incidents = self.coordinator.data.get("incidents", [])
        
        attributes = {
            "total_incidents": self.coordinator.data.get("total_count", 0),
            "filtered_incidents": self.coordinator.data.get("filtered_count", 0),
            "last_update": self.coordinator.data.get("last_update"),
            "source": self.coordinator.data.get("source"),
        }
        
        # Add detailed incident list
        incident_list = []
        for incident in incidents:
            incident_info = {
                "id": incident["id"],
                "incident_type": incident["incident_type"],
                "incident_type_detail": incident.get("incident_type_detail"),
                "location": incident["location"],
                "district": incident["district"],
                "text": incident["text"],
                "start_time": incident["start_time"],
                "status": incident.get("status", "Unknown"), # Added Status
                "unit_count": incident["unit_count"],
                "units": incident.get("units", []), # Added list of unit names
            }
            
            if incident.get("alarm_level"):
                incident_info["alarm_level"] = incident["alarm_level"]
            
            # Pass lat/lon exactly as they are in the coordinator
            if incident.get("lat") and incident.get("lon"):
                incident_info["lat"] = incident["lat"]
                incident_info["lon"] = incident["lon"]
            
            incident_list.append(incident_info)
        
        attributes["incidents"] = incident_list
        
        # Add summary by type
        type_counts = {}
        for incident in incidents:
            incident_type = incident["incident_type"]
            type_counts[incident_type] = type_counts.get(incident_type, 0) + 1
        
        attributes["incidents_by_type"] = type_counts
        
        return attributes


class OOELFVCountSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing total incident count."""

    _attr_icon = "mdi:counter"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: OOELFVDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "Total Incidents"
        self._attr_unique_id = f"{entry.entry_id}_total_count"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data["name"],
            "manufacturer": "OÖ Landes-Feuerwehrverband",
            "model": "Fire Brigade Incidents",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> int:
        """Return the total number of incidents."""
        if not self.coordinator.data:
            return 0
        return self.coordinator.data.get("total_count", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}
        
        return {
            "filtered_count": self.coordinator.data.get("filtered_count", 0),
            "last_update": self.coordinator.data.get("last_update"),
            "pub_date": self.coordinator.data.get("pub_date"),
        }
