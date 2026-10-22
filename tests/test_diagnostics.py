"""Test of the diagnostics download."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .common import FIRE_ID, setup_integration


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    feed_mock: AiohttpClientMocker,
) -> None:
    entry = await setup_integration(hass)

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["entry"]["title"] == "Feuerwehr OÖ"
    assert result["update_interval_seconds"] == 60
    assert result["feed"] == {
        "published": "2026-10-22T12:51:01+02:00",
        "incidents_in_feed": 7,
        "matching": 1,
        "shown": 1,
    }
    assert [incident["id"] for incident in result["incidents"]] == [FIRE_ID]
