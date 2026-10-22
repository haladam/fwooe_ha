"""Tests of the event entity that announces new and escalated incidents."""

from __future__ import annotations

import copy

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.fwooe_ha.const import EVENT_ALARM_RAISED, EVENT_NEW_INCIDENT

from .common import FIRE_ID, entity_id, feed_copy, incident_entry, refresh, serve, setup_integration


def add_second_fire(feed: dict) -> str:
    """Add another fire to the feed; returns its id."""
    second = copy.deepcopy(incident_entry(feed, FIRE_ID))
    second["num1"] = "E261004999"
    second["startzeit"] = "Thu, 22 Oct 2026 13:05:00 +0200"
    second["alarmstufe"] = "1"
    feed["einsaetze"]["7"] = {"einsatz": second}
    return second["num1"]


async def test_no_event_for_incidents_that_are_already_running_at_start(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer
) -> None:
    serve(aioclient_mock)
    entry = await setup_integration(hass)
    event_id = entity_id(hass, entry, "event", "incident_event")
    assert hass.states.get(event_id).state == "unknown"

    # the same feed again: still nothing
    await refresh(hass, freezer)
    assert hass.states.get(event_id).state == "unknown"


async def test_event_for_a_new_incident(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer
) -> None:
    serve(aioclient_mock)
    entry = await setup_integration(hass)
    event_id = entity_id(hass, entry, "event", "incident_event")

    feed = feed_copy()
    new_id = add_second_fire(feed)
    serve(aioclient_mock, feed)
    await refresh(hass, freezer)

    state = hass.states.get(event_id)
    assert state.state != "unknown"
    assert state.attributes["event_type"] == EVENT_NEW_INCIDENT
    assert state.attributes["id"] == new_id
    assert state.attributes["description"] == "Brand Industrie - Brand Gewerbe"
    assert state.attributes["alarm_level"] == 1


async def test_event_when_the_alarm_level_goes_up(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer
) -> None:
    serve(aioclient_mock)
    entry = await setup_integration(hass)
    event_id = entity_id(hass, entry, "event", "incident_event")

    feed = feed_copy()
    incident_entry(feed, FIRE_ID)["alarmstufe"] = "4"
    serve(aioclient_mock, feed)
    await refresh(hass, freezer)

    state = hass.states.get(event_id)
    assert state.attributes["event_type"] == EVENT_ALARM_RAISED
    assert state.attributes["id"] == FIRE_ID
    assert state.attributes["alarm_level"] == 4


async def test_no_event_when_the_alarm_level_goes_down(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer
) -> None:
    serve(aioclient_mock)
    entry = await setup_integration(hass)
    event_id = entity_id(hass, entry, "event", "incident_event")

    feed = feed_copy()
    incident_entry(feed, FIRE_ID)["alarmstufe"] = "1"
    serve(aioclient_mock, feed)
    await refresh(hass, freezer)

    assert hass.states.get(event_id).state == "unknown"
