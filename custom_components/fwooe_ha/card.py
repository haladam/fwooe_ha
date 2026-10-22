"""Serve the dashboard card that ships with the integration, and tell the frontend about it."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILE = Path(__file__).parent / "frontend" / "fwooe-incidents-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILE.name}"


async def async_register_card(hass: HomeAssistant) -> None:
    """Make ``fwooe-incidents-card`` available on every dashboard.

    Does nothing when Home Assistant runs without a frontend (no ``http`` or ``frontend``
    integration): the sensors work either way.
    """
    if getattr(hass, "http", None) is None or "frontend" not in hass.config.components:
        _LOGGER.debug("No frontend: the dashboard card is not registered")
        return
    if not CARD_FILE.is_file():
        _LOGGER.warning("The dashboard card %s is missing from the installation", CARD_FILE)
        return

    version = (await async_get_integration(hass, DOMAIN)).version
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=False)]
    )
    # The version in the URL makes the browser fetch the new card after an update.
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")
