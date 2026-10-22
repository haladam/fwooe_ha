"""DataUpdateCoordinator for the Feuerwehr OÖ Einsätze integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FwooeClient, FwooeConnectionError
from .const import (
    CONF_DISTRICTS,
    CONF_INCLUDE_SELF_INITIATED,
    CONF_KEYWORDS,
    CONF_MAX_INCIDENTS,
    CONF_MIN_ALARM_LEVEL,
    CONF_SCAN_INTERVAL,
    DEFAULT_MAX_INCIDENTS,
    DEFAULT_MIN_ALARM_LEVEL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .models import FeedFormatError, Incident, IncidentFilter, detect_changes

_LOGGER = logging.getLogger(__name__)

type FwooeConfigEntry = ConfigEntry[FwooeCoordinator]


@dataclass(frozen=True, slots=True)
class FwooeData:
    """What one update yields."""

    feed_total: int  # every running incident in the feed, filtered or not
    published: datetime | None  # when the feed says it was generated
    matching_count: int  # incidents that pass the filter
    incidents: tuple[Incident, ...]  # the newest of them, at most ``max_incidents``
    new: tuple[Incident, ...] = ()  # matching incidents first seen in this update
    raised: tuple[Incident, ...] = ()  # matching incidents whose alarm level went up


def filter_from_options(options: Mapping[str, Any]) -> IncidentFilter:
    """Build the incident filter from a config entry's options."""
    return IncidentFilter.create(
        districts=options.get(CONF_DISTRICTS),
        keywords=options.get(CONF_KEYWORDS),
        include_self_initiated=bool(options.get(CONF_INCLUDE_SELF_INITIATED, False)),
        min_alarm_level=options.get(CONF_MIN_ALARM_LEVEL, DEFAULT_MIN_ALARM_LEVEL),
        max_incidents=options.get(CONF_MAX_INCIDENTS, DEFAULT_MAX_INCIDENTS),
    )


def scan_interval_from_options(options: Mapping[str, Any]) -> timedelta:
    """The polling interval of a config entry, kept within the allowed range."""
    try:
        seconds = int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    except (TypeError, ValueError):
        seconds = DEFAULT_SCAN_INTERVAL
    return timedelta(seconds=max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, seconds)))


class FwooeCoordinator(DataUpdateCoordinator[FwooeData]):
    """Polls the feed, applies the filters and notices new and escalated incidents."""

    config_entry: FwooeConfigEntry

    def __init__(self, hass: HomeAssistant, entry: FwooeConfigEntry, client: FwooeClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=scan_interval_from_options(entry.options),
            # listeners are only called when something changed
            always_update=False,
        )
        self.client = client
        self.incident_filter = filter_from_options(entry.options)
        # id -> alarm level of the matching incidents of the previous update;
        # None until the first update, so incidents already running at start-up are
        # not announced as new.
        self._known: dict[str, int] | None = None

    async def _async_update_data(self) -> FwooeData:
        """Fetch the feed and apply the filters."""
        try:
            feed = await self.client.async_get_feed()
        except FwooeConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err
        except FeedFormatError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_data",
                translation_placeholders={"error": str(err)},
            ) from err

        selection = self.incident_filter.select(feed.incidents)
        new, raised = detect_changes(self._known, selection.matching)
        self._known = {incident.id: incident.alarm_level or 0 for incident in selection.matching}
        if new or raised:
            _LOGGER.debug("%s: %d new and %d escalated incidents", self.name, len(new), len(raised))

        return FwooeData(
            feed_total=len(feed.incidents),
            published=feed.published,
            matching_count=len(selection.matching),
            incidents=selection.shown,
            new=new,
            raised=raised,
        )
