"""Tests of the map entities: one per incident, gone when the incident ends."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.fwooe_ha.const import (
    CONF_DISTRICTS,
    CONF_INCLUDE_SELF_INITIATED,
    CONF_NAME,
    DOMAIN,
)

from .common import FIRE_ID, feed_copy, refresh, serve, setup_integration


def geo_states(hass: HomeAssistant):
    return hass.states.async_all("geo_location")


def geo_registry_entries(hass: HomeAssistant):
    return [
        entry for entry in er.async_get(hass).entities.values() if entry.domain == "geo_location"
    ]


async def test_an_entity_for_the_fire(hass: HomeAssistant, feed_mock: AiohttpClientMocker) -> None:
    await setup_integration(hass)

    (state,) = geo_states(hass)
    # entity name = incident; the friendly name starts with the name of the device
    assert state.name == "Feuerwehr OÖ Brand Industrie - Brand Gewerbe (Katsdorf)"
    assert state.attributes["source"] == DOMAIN
    assert state.attributes["latitude"] == 48.3122
    assert state.attributes["longitude"] == 14.5091
    assert state.attributes["unit_of_measurement"] == "km"
    assert state.attributes["icon"] == "mdi:fire"
    assert state.attributes["alarm_level"] == 3
    assert state.attributes["district"] == "Perg"
    assert state.attributes["id"] == FIRE_ID
    assert float(state.state) > 0  # distance from home


async def test_an_entity_per_incident(hass: HomeAssistant, feed_mock: AiohttpClientMocker) -> None:
    await setup_integration(hass, {CONF_INCLUDE_SELF_INITIATED: True})
    assert len(geo_states(hass)) == 7


async def test_only_the_chosen_bezirke_get_entities(
    hass: HomeAssistant, feed_mock: AiohttpClientMocker
) -> None:
    await setup_integration(
        hass, {CONF_INCLUDE_SELF_INITIATED: True, CONF_DISTRICTS: ["PE-07", "SE-11"]}
    )
    assert {state.attributes["district"] for state in geo_states(hass)} == {"Perg", "Steyr-Land"}
    assert len(geo_states(hass)) == 2


async def test_changing_the_bezirke_removes_the_entities_of_the_others(
    hass: HomeAssistant, feed_mock: AiohttpClientMocker
) -> None:
    entry = await setup_integration(hass, {CONF_INCLUDE_SELF_INITIATED: True})
    assert len(geo_states(hass)) == 7

    hass.config_entries.async_update_entry(
        entry, options={CONF_INCLUDE_SELF_INITIATED: True, CONF_DISTRICTS: ["VB-13"]}
    )
    await hass.async_block_till_done()  # the update listener reloads the entry

    assert {state.attributes["district"] for state in geo_states(hass)} == {"Vöcklabruck"}
    assert len(geo_states(hass)) == 2  # both incidents in Ottnang
    assert len(geo_registry_entries(hass)) == 2  # the others are not left behind


async def test_entity_disappears_when_the_incident_ends_and_returns_with_it(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, freezer
) -> None:
    serve(aioclient_mock)
    await setup_integration(hass)
    assert len(geo_states(hass)) == 1
    assert len(geo_registry_entries(hass)) == 1

    ended = feed_copy()
    ended["einsaetze"] = {
        key: value
        for key, value in ended["einsaetze"].items()
        if value["einsatz"]["num1"] != FIRE_ID
    }
    serve(aioclient_mock, ended)
    await refresh(hass, freezer)
    assert geo_states(hass) == []
    assert geo_registry_entries(hass) == []  # not left behind as an unavailable entity

    serve(aioclient_mock)
    await refresh(hass, freezer)
    assert len(geo_states(hass)) == 1


async def test_stale_registry_entries_are_removed_at_start(
    hass: HomeAssistant, feed_mock: AiohttpClientMocker
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Feuerwehr OÖ",
        unique_id="feuerwehr_oo",
        data={CONF_NAME: "Feuerwehr OÖ"},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "geo_location", DOMAIN, f"{entry.entry_id}_E-ENDED-LONG-AGO", config_entry=entry
    )
    assert len(geo_registry_entries(hass)) == 1

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    unique_ids = {item.unique_id for item in geo_registry_entries(hass)}
    assert unique_ids == {f"{entry.entry_id}_{FIRE_ID}"}
