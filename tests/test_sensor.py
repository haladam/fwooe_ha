"""Tests of the sensors and the binary sensor, and of what the filters do to them."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.fwooe_ha.const import (
    CONF_DISTRICTS,
    CONF_INCLUDE_SELF_INITIATED,
    CONF_KEYWORDS,
    CONF_MAX_INCIDENTS,
    CONF_MIN_ALARM_LEVEL,
)

from .common import FIRE_ID, NEWEST_SELF_INITIATED_ID, entity_id, setup_integration


async def test_default_filters_show_the_fire_only(
    hass: HomeAssistant, feed_mock: AiohttpClientMocker
) -> None:
    entry = await setup_integration(hass)

    incidents = hass.states.get(entity_id(hass, entry, "sensor", "incidents"))
    assert incidents.state == "1"
    assert [item["id"] for item in incidents.attributes["incidents"]] == [FIRE_ID]
    assert incidents.attributes["incidents_by_kind"] == {"BRAND": 1}

    latest = hass.states.get(entity_id(hass, entry, "sensor", "latest_incident"))
    assert latest.state == "Brand Industrie - Brand Gewerbe"
    assert latest.attributes["alarm_level"] == 3
    assert latest.attributes["district"] == "Perg"
    assert latest.attributes["unit_count"] == 16
    assert len(latest.attributes["units"]) == 16

    started = hass.states.get(entity_id(hass, entry, "sensor", "latest_incident_started"))
    assert started.state == "2026-10-22T04:28:48+00:00"  # 06:28:48 +02:00

    assert hass.states.get(entity_id(hass, entry, "sensor", "incidents_in_feed")).state == "7"
    published = hass.states.get(entity_id(hass, entry, "sensor", "feed_published"))
    assert published.state == "2026-10-22T10:51:01+00:00"

    active = hass.states.get(entity_id(hass, entry, "binary_sensor", "active_incident"))
    assert active.state == "on"
    assert active.attributes["count"] == 1


@pytest.mark.parametrize(
    ("options", "count", "shown"),
    [
        ({}, 1, [FIRE_ID]),
        ({CONF_INCLUDE_SELF_INITIATED: True}, 7, None),
        ({CONF_DISTRICTS: ["Perg"]}, 1, [FIRE_ID]),
        ({CONF_DISTRICTS: ["perg", "Freistadt"]}, 1, [FIRE_ID]),
        ({CONF_DISTRICTS: ["Freistadt"]}, 0, []),
        (
            {CONF_DISTRICTS: ["Freistadt"], CONF_INCLUDE_SELF_INITIATED: True},
            1,
            [NEWEST_SELF_INITIATED_ID],
        ),
        ({CONF_KEYWORDS: ["brand"]}, 1, [FIRE_ID]),
        ({CONF_KEYWORDS: ["verkehr"]}, 0, []),
        ({CONF_MIN_ALARM_LEVEL: 3}, 1, [FIRE_ID]),
        ({CONF_MIN_ALARM_LEVEL: 4}, 0, []),
        ({CONF_INCLUDE_SELF_INITIATED: True, CONF_MAX_INCIDENTS: 3}, 7, None),
    ],
)
async def test_filters(
    hass: HomeAssistant,
    feed_mock: AiohttpClientMocker,
    options: dict[str, Any],
    count: int,
    shown: list[str] | None,
) -> None:
    entry = await setup_integration(hass, options)

    incidents = hass.states.get(entity_id(hass, entry, "sensor", "incidents"))
    assert incidents.state == str(count)
    ids = [item["id"] for item in incidents.attributes["incidents"]]
    if shown is not None:
        assert ids == shown
    else:
        assert len(ids) == min(count, options.get(CONF_MAX_INCIDENTS, 20))
        assert ids[0] == NEWEST_SELF_INITIATED_ID  # newest first

    active = hass.states.get(entity_id(hass, entry, "binary_sensor", "active_incident"))
    assert active.state == ("on" if count else "off")


async def test_no_matching_incident(hass: HomeAssistant, feed_mock: AiohttpClientMocker) -> None:
    entry = await setup_integration(hass, {CONF_MIN_ALARM_LEVEL: 9})

    assert hass.states.get(entity_id(hass, entry, "sensor", "incidents")).state == "0"
    assert hass.states.get(entity_id(hass, entry, "sensor", "latest_incident")).state == "unknown"
    assert (
        hass.states.get(entity_id(hass, entry, "sensor", "latest_incident_started")).state
        == "unknown"
    )
    assert (
        hass.states.get(entity_id(hass, entry, "binary_sensor", "active_incident")).state == "off"
    )
    # the diagnostic sensors still describe the whole feed
    assert hass.states.get(entity_id(hass, entry, "sensor", "incidents_in_feed")).state == "7"
