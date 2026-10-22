"""Fixtures for the tests."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .common import serve


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components/."""


@pytest.fixture
def feed_mock(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """The mocked feed answers with the fixture feed."""
    serve(aioclient_mock)
    return aioclient_mock
