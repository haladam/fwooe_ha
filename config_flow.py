"""Config flow for Upper Austria Fire Brigade integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_FILTER_DISTRICTS,
    CONF_FILTER_KEYWORDS,
    CONF_MAX_INCIDENTS,
    CONF_NAME,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_FILTER_DISTRICTS, default=""): cv.string,
        vol.Optional(CONF_FILTER_KEYWORDS, default=""): cv.string,
        vol.Optional(CONF_MAX_INCIDENTS, default=20): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
    }
)


class OOELFVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Upper Austria Fire Brigade."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Create unique ID based on name
                await self.async_set_unique_id(user_input[CONF_NAME].lower().replace(" ", "_"))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "districts_help": "Comma-separated list of districts (e.g., 'Gmunden, Vöcklabruck')",
                "keywords_help": "Comma-separated keywords to filter incidents (e.g., 'Brand, Unfall')",
            },
        )
