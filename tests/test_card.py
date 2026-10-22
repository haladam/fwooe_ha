"""Tests that the dashboard card is served and registered with the frontend.

What the card shows is tested by ``tests/card.test.mjs`` (plain Node).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.fwooe_ha.card import CARD_FILE, CARD_URL

from .common import entity_id, setup_integration

MANIFEST = Path(__file__).parent.parent / "custom_components" / "fwooe_ha" / "manifest.json"


async def test_the_card_is_served_and_registered_once(
    hass: HomeAssistant, feed_mock: AiohttpClientMocker
) -> None:
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    hass.config.components.add("frontend")
    version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]

    with patch("custom_components.fwooe_ha.card.add_extra_js_url") as add_url:
        entry = await setup_integration(hass)
        # a reload of the entry must not register it again
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    hass.http.async_register_static_paths.assert_awaited_once()
    (config,) = hass.http.async_register_static_paths.await_args.args[0]
    assert config.url_path == "/fwooe_ha/fwooe-incidents-card.js" == CARD_URL
    assert config.path == str(CARD_FILE)
    assert Path(config.path).is_file()
    add_url.assert_called_once_with(hass, f"{CARD_URL}?v={version}")


async def test_without_a_frontend_nothing_is_registered_and_the_sensors_work(
    hass: HomeAssistant, feed_mock: AiohttpClientMocker
) -> None:
    hass.http = MagicMock(async_register_static_paths=AsyncMock())  # but no "frontend"

    with patch("custom_components.fwooe_ha.card.add_extra_js_url") as add_url:
        entry = await setup_integration(hass)

    hass.http.async_register_static_paths.assert_not_awaited()
    add_url.assert_not_called()
    assert hass.states.get(entity_id(hass, entry, "sensor", "incidents")).state == "1"


def test_the_card_file_is_a_module_that_defines_the_card() -> None:
    source = CARD_FILE.read_text(encoding="utf-8")
    assert 'export const CARD_TYPE = "fwooe-incidents-card"' in source
    assert "customElements.define(CARD_TYPE" in source
    assert "window.customCards" in source
