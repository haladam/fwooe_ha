"""Helpers shared by the Home Assistant tests."""

from __future__ import annotations

import copy
from datetime import timedelta
import json
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.fwooe_ha.const import API_URL, CONF_NAME, DEFAULT_SCAN_INTERVAL, DOMAIN

FEED: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "feed.json").read_text(encoding="utf-8")
)

# The industrial fire in the fixture and the newest of the self-initiated deployments.
FIRE_ID = "E261004261"
NEWEST_SELF_INITIATED_ID = "E261004313"


def feed_copy() -> dict[str, Any]:
    """A fresh copy of the fixture feed that a test may change."""
    return copy.deepcopy(FEED)


def incident_entry(feed: dict[str, Any], incident_id: str) -> dict[str, Any]:
    """The ``einsatz`` object of an incident in a feed."""
    for entry in feed["einsaetze"].values():
        if entry["einsatz"]["num1"] == incident_id:
            return entry["einsatz"]
    raise KeyError(incident_id)


def serve(
    aioclient_mock: AiohttpClientMocker,
    feed: dict[str, Any] | None = None,
    *,
    status: int = 200,
    text: str | None = None,
) -> None:
    """Make the mocked feed URL answer with a feed, an error status or raw text."""
    aioclient_mock.clear_requests()
    body = text if text is not None else json.dumps(feed if feed is not None else FEED)
    aioclient_mock.get(API_URL, status=status, text=body)


async def setup_integration(
    hass: HomeAssistant, options: dict[str, Any] | None = None
) -> MockConfigEntry:
    """Set up a config entry with the given options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Feuerwehr OÖ",
        unique_id="feuerwehr_oo",
        data={CONF_NAME: "Feuerwehr OÖ"},
        options=options or {},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity_id(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> str:
    """The entity id of an entity of the entry, found by its unique id."""
    found = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert found is not None, f"no {platform} entity {key}"
    return found


async def refresh(hass: HomeAssistant, freezer: Any) -> None:
    """Let the polling interval pass, so the coordinator reads the feed again."""
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
