"""Diagnostics for the Feuerwehr OÖ Einsätze integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import FwooeConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FwooeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics: the configuration and what the last update found.

    The incidents come from a public feed, so nothing here needs redacting.
    """
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "update_interval_seconds": (
            coordinator.update_interval.total_seconds() if coordinator.update_interval else None
        ),
        "feed": {
            "published": data.published.isoformat() if data.published else None,
            "incidents_in_feed": data.feed_total,
            "matching": data.matching_count,
            "shown": len(data.incidents),
        },
        "incidents": [incident.as_dict() for incident in data.incidents],
    }
