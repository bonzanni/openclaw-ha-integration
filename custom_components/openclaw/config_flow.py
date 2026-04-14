"""Config flow for OpenClaw integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import AuthenticationError, OpenClawApiClient
from .const import (
    CONF_AGENT_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_SESSION_MODE,
    CONF_TOKEN,
    DEFAULT_AGENT_ID,
    DEFAULT_PORT,
    DEFAULT_SESSION_MODE,
    DOMAIN,
    SESSION_MODE_CONVERSATION,
    SESSION_MODE_DEVICE,
    SESSION_MODE_USER,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="localhost"): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_TOKEN): str,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): str,
    }
)


class OpenClawConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenClaw."""

    VERSION = 1

    _host: str
    _port: int
    _token: str
    _discovery_name: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                client = OpenClawApiClient(
                    session=async_get_clientsession(self.hass),
                    host=user_input[CONF_HOST],
                    port=user_input[CONF_PORT],
                    token=user_input[CONF_TOKEN],
                )
                await client.list_models()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="OpenClaw",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle Supervisor add-on discovery."""
        self._host = discovery_info.config["host"]
        self._port = discovery_info.config["port"]
        self._token = discovery_info.config["token"]
        self._discovery_name = discovery_info.name

        await self.async_set_unique_id(discovery_info.uuid)
        self._abort_if_unique_id_configured()

        self.context.update(
            {
                "title_placeholders": {"name": discovery_info.name},
                "configuration_url": (
                    f"homeassistant://hassio/addon/{discovery_info.slug}/info"
                ),
            }
        )

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm add-on discovery with retry for gateway startup race."""
        errors: dict[str, str] = {}

        if user_input is not None:
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    client = OpenClawApiClient(
                        session=async_get_clientsession(self.hass),
                        host=self._host,
                        port=self._port,
                        token=self._token,
                    )
                    await client.list_models()
                    last_error = None
                    break
                except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                    last_error = err
                    if attempt < 2:
                        await asyncio.sleep(2)

            if last_error is not None:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=self._discovery_name,
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_TOKEN: self._token,
                    },
                )

        return self.async_show_form(
            step_id="hassio_confirm",
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth when token becomes invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth with new token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            try:
                client = OpenClawApiClient(
                    session=async_get_clientsession(self.hass),
                    host=reauth_entry.data[CONF_HOST],
                    port=reauth_entry.data[CONF_PORT],
                    token=user_input[CONF_TOKEN],
                )
                await client.list_models()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_TOKEN: user_input[CONF_TOKEN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OpenClawOptionsFlow:
        """Get the options flow handler."""
        return OpenClawOptionsFlow()


class OpenClawOptionsFlow(OptionsFlow):
    """Handle OpenClaw options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_AGENT_ID,
                            default=DEFAULT_AGENT_ID,
                        ): str,
                        vol.Optional(
                            CONF_SESSION_MODE,
                            default=DEFAULT_SESSION_MODE,
                        ): vol.In(
                            {
                                SESSION_MODE_DEVICE: "Per device",
                                SESSION_MODE_USER: "Per user",
                                SESSION_MODE_CONVERSATION: "Per conversation",
                            }
                        ),
                    }
                ),
                self.config_entry.options,
            ),
        )
