"""Tests of the config flow and the options flow."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import slugify
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.fwooe_ha.const import (
    CONF_DISTRICTS,
    CONF_INCLUDE_SELF_INITIATED,
    CONF_KEYWORDS,
    CONF_MAX_INCIDENTS,
    CONF_MIN_ALARM_LEVEL,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DOMAIN,
)

from .common import entity_id, serve, setup_integration


async def start_user_flow(hass: HomeAssistant) -> dict:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def test_user_flow_creates_an_entry(
    hass: HomeAssistant, feed_mock: AiohttpClientMocker
) -> None:
    result = await start_user_flow(hass)

    with patch("custom_components.fwooe_ha.async_setup_entry", return_value=True) as setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Bezirk Perg",
                CONF_DISTRICTS: ["Perg"],
                CONF_INCLUDE_SELF_INITIATED: False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bezirk Perg"
    assert result["data"] == {CONF_NAME: "Bezirk Perg"}
    assert result["options"] == {CONF_DISTRICTS: ["Perg"], CONF_INCLUDE_SELF_INITIATED: False}
    assert len(setup.mock_calls) == 1


async def test_cannot_connect_can_be_retried(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    serve(aioclient_mock, status=500)
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: DEFAULT_NAME}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    serve(aioclient_mock)
    with patch("custom_components.fwooe_ha.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_NAME: DEFAULT_NAME}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_invalid_data(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    serve(aioclient_mock, text="<html>Wartungsarbeiten</html>")
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: DEFAULT_NAME}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_data"}


async def test_the_same_name_cannot_be_added_twice(
    hass: HomeAssistant, feed_mock: AiohttpClientMocker
) -> None:
    MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        unique_id=slugify(DEFAULT_NAME),
        data={CONF_NAME: DEFAULT_NAME},
    ).add_to_hass(hass)
    result = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: DEFAULT_NAME}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_changes_the_filters_and_reloads(
    hass: HomeAssistant, feed_mock: AiohttpClientMocker
) -> None:
    entry = await setup_integration(hass)
    incidents = entity_id(hass, entry, "sensor", "incidents")
    assert hass.states.get(incidents).state == "1"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_DISTRICTS: ["Freistadt"],
            CONF_KEYWORDS: [],
            CONF_INCLUDE_SELF_INITIATED: True,
            CONF_MIN_ALARM_LEVEL: 0,
            CONF_MAX_INCIDENTS: 5,
            CONF_SCAN_INTERVAL: 120,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DISTRICTS] == ["Freistadt"]
    assert entry.options[CONF_MAX_INCIDENTS] == 5
    assert isinstance(entry.options[CONF_SCAN_INTERVAL], int)

    # the entry was reloaded with the new filters
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(incidents).state == "1"
    assert hass.states.get(incidents).attributes["incidents"][0]["district"] == "Freistadt"
    assert entry.runtime_data.update_interval == timedelta(seconds=120)
