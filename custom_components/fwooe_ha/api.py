"""Client for the public incident feed of the Oö. Landes-Feuerwehrverband."""

from __future__ import annotations

import asyncio
import json

import aiohttp

from .const import API_TIMEOUT, API_URL
from .models import Feed, FeedFormatError, parse_feed


class FwooeConnectionError(Exception):
    """The feed could not be fetched (network, timeout or an HTTP error status)."""


class FwooeClient:
    """Fetches and parses the running-incident feed."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize with the shared Home Assistant HTTP session."""
        self._session = session

    async def async_get_feed(self) -> Feed:
        """Return the current feed.

        Raises FwooeConnectionError when it cannot be fetched and FeedFormatError when
        what came back is not the incident feed.
        """
        try:
            async with (
                asyncio.timeout(API_TIMEOUT),
                self._session.get(
                    API_URL, headers={"Accept": "application/json, text/plain, */*"}
                ) as response,
            ):
                if response.status != 200:
                    raise FwooeConnectionError(f"HTTP {response.status}")
                # The feed is served as text/plain; read the bytes and let json decode
                # them (UTF-8) instead of having aiohttp guess a charset.
                body = await response.read()
        except TimeoutError as err:
            raise FwooeConnectionError("the request timed out") from err
        except aiohttp.ClientError as err:
            raise FwooeConnectionError(str(err) or type(err).__name__) from err

        try:
            raw = json.loads(body)
        except ValueError as err:  # JSONDecodeError and UnicodeDecodeError
            raise FeedFormatError(f"not valid JSON ({err})") from err
        return parse_feed(raw)
