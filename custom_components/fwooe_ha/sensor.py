"""Sensors of the Feuerwehr OÖ Einsätze integration."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import FwooeConfigEntry, FwooeCoordinator, FwooeData
from .entity import FwooeEntity
from .models import Incident

# The state of a sensor is limited to 255 characters.
MAX_STATE_LENGTH = 255


def _latest(data: FwooeData) -> Incident | None:
    return data.incidents[0] if data.incidents else None


def _latest_description(data: FwooeData) -> str | None:
    latest = _latest(data)
    return latest.description[:MAX_STATE_LENGTH] if latest else None


def _latest_start(data: FwooeData) -> datetime | None:
    latest = _latest(data)
    return latest.start if latest else None


def _incidents_attributes(data: FwooeData) -> dict[str, Any]:
    return {
        "incidents": [incident.as_dict() for incident in data.incidents],
        "incidents_by_kind": dict(Counter(incident.kind for incident in data.incidents)),
    }


def _latest_attributes(data: FwooeData) -> dict[str, Any]:
    latest = _latest(data)
    return latest.as_dict() if latest else {}


@dataclass(frozen=True, kw_only=True)
class FwooeSensorDescription(SensorEntityDescription):
    """Describes a sensor of the feed."""

    value_fn: Callable[[FwooeData], StateType | datetime]
    attributes_fn: Callable[[FwooeData], dict[str, Any]] | None = None


SENSORS: tuple[FwooeSensorDescription, ...] = (
    FwooeSensorDescription(
        key="incidents",
        translation_key="incidents",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.matching_count,
        attributes_fn=_incidents_attributes,
    ),
    FwooeSensorDescription(
        key="latest_incident",
        translation_key="latest_incident",
        value_fn=_latest_description,
        attributes_fn=_latest_attributes,
    ),
    FwooeSensorDescription(
        key="latest_incident_started",
        translation_key="latest_incident_started",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_latest_start,
    ),
    FwooeSensorDescription(
        key="incidents_in_feed",
        translation_key="incidents_in_feed",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.feed_total,
    ),
    FwooeSensorDescription(
        key="feed_published",
        translation_key="feed_published",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.published,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FwooeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(FwooeSensor(coordinator, description) for description in SENSORS)


class FwooeSensor(FwooeEntity, SensorEntity):
    """A sensor of the feed."""

    entity_description: FwooeSensorDescription

    # The incident list and the brigades are long and change with every incident: show
    # them, but do not write them to the database with every state.
    _unrecorded_attributes = frozenset({"incidents", "incidents_by_kind", "units"})

    def __init__(self, coordinator: FwooeCoordinator, description: FwooeSensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the attributes of the sensor."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)
