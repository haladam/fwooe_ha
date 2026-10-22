"""Config flow and options flow of the Feuerwehr OÖ Einsätze integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import slugify
import voluptuous as vol

from .api import FwooeClient, FwooeConnectionError
from .const import (
    CONF_DISTRICTS,
    CONF_INCLUDE_SELF_INITIATED,
    CONF_KEYWORDS,
    CONF_MAX_INCIDENTS,
    CONF_MIN_ALARM_LEVEL,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_MAX_INCIDENTS,
    DEFAULT_MIN_ALARM_LEVEL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DISTRICTS,
    DOMAIN,
    MAX_ALARM_LEVEL,
    MAX_MAX_INCIDENTS,
    MAX_SCAN_INTERVAL,
    MIN_MAX_INCIDENTS,
    MIN_SCAN_INTERVAL,
)
from .models import FeedFormatError

_LOGGER = logging.getLogger(__name__)

_INTEGER_OPTIONS = (CONF_MIN_ALARM_LEVEL, CONF_MAX_INCIDENTS, CONF_SCAN_INTERVAL)


def _districts_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=list(DISTRICTS),
            multiple=True,
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _keywords_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[], multiple=True, custom_value=True, mode=SelectSelectorMode.DROPDOWN
        )
    )


def _number(minimum: int, maximum: int, step: int = 1, unit: str | None = None):
    config = NumberSelectorConfig(min=minimum, max=maximum, step=step, mode=NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Optional(CONF_DISTRICTS): _districts_selector(),
        vol.Optional(CONF_INCLUDE_SELF_INITIATED, default=False): BooleanSelector(),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DISTRICTS): _districts_selector(),
        vol.Optional(CONF_KEYWORDS): _keywords_selector(),
        vol.Optional(CONF_INCLUDE_SELF_INITIATED, default=False): BooleanSelector(),
        vol.Optional(CONF_MIN_ALARM_LEVEL, default=DEFAULT_MIN_ALARM_LEVEL): _number(
            0, MAX_ALARM_LEVEL
        ),
        vol.Optional(CONF_MAX_INCIDENTS, default=DEFAULT_MAX_INCIDENTS): _number(
            MIN_MAX_INCIDENTS, MAX_MAX_INCIDENTS
        ),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): _number(
            MIN_SCAN_INTERVAL, MAX_SCAN_INTERVAL, step=5, unit="s"
        ),
    }
)


def _clean_options(user_input: dict[str, Any]) -> dict[str, Any]:
    """Number selectors return floats; store whole numbers."""
    options = dict(user_input)
    for key in _INTEGER_OPTIONS:
        if key in options:
            options[key] = int(options[key])
    return options


async def _async_check_feed(hass: HomeAssistant) -> str | None:
    """Try to read the feed; return a form error key, or None when it works."""
    client = FwooeClient(async_get_clientsession(hass))
    try:
        await client.async_get_feed()
    except FwooeConnectionError:
        return "cannot_connect"
    except FeedFormatError:
        return "invalid_data"
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error while reading the incident feed")
        return "unknown"
    return None


class FwooeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a feed (with its filters) as a config entry."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> FwooeOptionsFlow:
        """Return the options flow."""
        return FwooeOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the first and only step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip() or DEFAULT_NAME
            await self.async_set_unique_id(slugify(name) or DOMAIN)
            self._abort_if_unique_id_configured()

            if (error := await _async_check_feed(self.hass)) is None:
                options = _clean_options(
                    {key: value for key, value in user_input.items() if key != CONF_NAME}
                )
                return self.async_create_entry(title=name, data={CONF_NAME: name}, options=options)
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )


class FwooeOptionsFlow(OptionsFlow):
    """Change the filters and the polling interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=_clean_options(user_input))

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
