"""OpenClaw integration for Home Assistant."""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AuthenticationError, OpenClawApiClient
from .const import CONF_HOST, CONF_PORT, CONF_TOKEN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CONVERSATION]

type OpenClawConfigEntry = ConfigEntry[OpenClawApiClient]


async def async_setup_entry(
    hass: HomeAssistant, entry: OpenClawConfigEntry
) -> bool:
    """Set up OpenClaw from a config entry."""
    client = OpenClawApiClient(
        session=async_get_clientsession(hass),
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        token=entry.data[CONF_TOKEN],
    )

    try:
        await client.health_check()
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        raise ConfigEntryNotReady("OpenClaw gateway not reachable") from err
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed("Invalid gateway token") from err

    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: OpenClawConfigEntry
) -> bool:
    """Unload OpenClaw config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
