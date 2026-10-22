"""Tests of setting up and unloading the integration."""

from __future__ import annotations

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.fwooe_ha.const import API_URL

from .common import entity_id, refresh, serve, setup_integration


async def test_setup_and_unload(hass: HomeAssistant, feed_mock: AiohttpClientMocker) -> None:
    entry = await setup_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_retries_when_the_feed_returns_an_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    serve(aioclient_mock, status=500)
    entry = await setup_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_retries_when_the_connection_fails(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(API_URL, exc=aiohttp.ClientError("no route"))
    entry = await setup_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_retries_when_the_feed_is_not_the_incident_feed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    serve(aioclient_mock, text="<html>Wartungsarbeiten</html>")
    entry = await setup_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_entities_become_unavailable_and_recover(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer
) -> None:
    serve(aioclient_mock)
    entry = await setup_integration(hass)
    incidents = entity_id(hass, entry, "sensor", "incidents")
    assert hass.states.get(incidents).state == "1"

    serve(aioclient_mock, status=503)
    await refresh(hass, freezer)
    assert hass.states.get(incidents).state == "unavailable"

    serve(aioclient_mock)
    await refresh(hass, freezer)
    assert hass.states.get(incidents).state == "1"
