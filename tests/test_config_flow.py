"""Tests for OpenClaw config flow."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

# ---------------------------------------------------------------------------
# Stub out homeassistant modules so config_flow.py can be imported without
# a real HA installation.
# ---------------------------------------------------------------------------

def _make_stub_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


def _ensure_ha_stubs() -> None:
    """Create the minimal sys.modules stubs required by config_flow imports."""
    if "homeassistant" in sys.modules:
        return  # real HA is installed – nothing to stub

    # homeassistant (top-level)
    ha = _make_stub_module("homeassistant")

    # homeassistant.core
    ha_core = _make_stub_module("homeassistant.core")
    ha_core.callback = lambda f: f  # decorator no-op

    # homeassistant.config_entries
    ha_ce = _make_stub_module("homeassistant.config_entries")

    class _ConfigFlowResult(dict):
        pass

    class _ConfigFlow:
        """Minimal ConfigFlow stub."""

        def __init_subclass__(cls, domain: str | None = None, **kwargs: object) -> None:
            super().__init_subclass__(**kwargs)
            if domain is not None:
                cls._domain = domain

        def __init__(self) -> None:
            self.hass = None
            self.context: dict = {}

        def async_show_form(self, *, step_id, data_schema=None, errors=None, **kw):
            return _ConfigFlowResult(
                type="form",
                step_id=step_id,
                data_schema=data_schema,
                errors=errors or {},
            )

        def async_create_entry(self, *, title, data, **kw):
            return _ConfigFlowResult(type="create_entry", title=title, data=data)

        def async_abort(self, *, reason):
            return _ConfigFlowResult(type="abort", reason=reason)

        async def async_set_unique_id(self, unique_id):
            pass

        def _abort_if_unique_id_configured(self):
            pass

        def _get_reauth_entry(self):
            return MagicMock()

        def async_update_reload_and_abort(self, entry, *, data_updates=None, **kw):
            return _ConfigFlowResult(type="abort", reason="reauth_successful")

    class _OptionsFlow:
        """Minimal OptionsFlow stub."""

        def __init__(self) -> None:
            self.config_entry = MagicMock()
            self.config_entry.options = {}

        def async_show_form(self, *, step_id, data_schema=None, errors=None, **kw):
            return _ConfigFlowResult(
                type="form",
                step_id=step_id,
                data_schema=data_schema,
                errors=errors or {},
            )

        def async_create_entry(self, *, data, **kw):
            return _ConfigFlowResult(type="create_entry", data=data)

        def add_suggested_values_to_schema(self, schema, suggested_values):
            return schema

    ha_ce.ConfigFlow = _ConfigFlow
    ha_ce.OptionsFlow = _OptionsFlow
    ha_ce.ConfigEntry = MagicMock
    ha_ce.ConfigFlowResult = _ConfigFlowResult

    # homeassistant.helpers
    ha_helpers = _make_stub_module("homeassistant.helpers")

    # homeassistant.helpers.aiohttp_client
    ha_aiohttp = _make_stub_module("homeassistant.helpers.aiohttp_client")
    ha_aiohttp.async_get_clientsession = MagicMock(return_value=MagicMock())

    # homeassistant.helpers.service_info  (parent)
    ha_si = _make_stub_module("homeassistant.helpers.service_info")

    # homeassistant.helpers.service_info.hassio
    ha_si_hassio = _make_stub_module("homeassistant.helpers.service_info.hassio")

    class _HassioServiceInfo:
        def __init__(self, config, name, slug, uuid):
            self.config = config
            self.name = name
            self.slug = slug
            self.uuid = uuid

    ha_si_hassio.HassioServiceInfo = _HassioServiceInfo

    # Wire sub-modules onto their parents so attribute access works too
    ha.core = ha_core
    ha.config_entries = ha_ce
    ha.helpers = ha_helpers
    ha_helpers.aiohttp_client = ha_aiohttp
    ha_helpers.service_info = ha_si
    ha_si.hassio = ha_si_hassio


_ensure_ha_stubs()

# Now it's safe to import the module under test
from custom_components.openclaw.config_flow import (  # noqa: E402
    OpenClawConfigFlow,
    OpenClawOptionsFlow,
)
from custom_components.openclaw.const import (  # noqa: E402
    CONF_AGENT_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_SESSION_MODE,
    CONF_TOKEN,
    DEFAULT_PORT,
    DOMAIN,
    SESSION_MODE_DEVICE,
)


MOCK_MODELS = [
    {"id": "openclaw/default", "object": "model"},
    {"id": "openclaw/butler", "object": "model"},
]


@pytest.fixture
def mock_api_client():
    """Create a mock OpenClawApiClient."""
    client = AsyncMock()
    client.list_models = AsyncMock(return_value=MOCK_MODELS)
    client.health_check = AsyncMock(return_value=True)
    return client


class TestUserFlow:
    """Tests for manual configuration flow."""

    @pytest.mark.asyncio
    async def test_successful_manual_entry(self, mock_api_client) -> None:
        """Test successful manual gateway configuration."""
        with patch(
            "custom_components.openclaw.config_flow.OpenClawApiClient",
            return_value=mock_api_client,
        ):
            flow = OpenClawConfigFlow()
            flow.hass = MagicMock()

            # First call — show form
            result = await flow.async_step_user(user_input=None)
            assert result["type"] == "form"
            assert result["step_id"] == "user"

            # Second call — submit valid data
            result = await flow.async_step_user(
                user_input={
                    CONF_HOST: "192.168.1.100",
                    CONF_PORT: DEFAULT_PORT,
                    CONF_TOKEN: "my-token",
                }
            )
            assert result["type"] == "create_entry"
            assert result["title"] == "OpenClaw"
            assert result["data"][CONF_HOST] == "192.168.1.100"
            assert result["data"][CONF_TOKEN] == "my-token"

    @pytest.mark.asyncio
    async def test_connection_error_shows_form(self, mock_api_client) -> None:
        """Test that connection failure re-shows form with error."""
        mock_api_client.list_models = AsyncMock(
            side_effect=aiohttp.ClientError("Connection refused")
        )
        with patch(
            "custom_components.openclaw.config_flow.OpenClawApiClient",
            return_value=mock_api_client,
        ):
            flow = OpenClawConfigFlow()
            flow.hass = MagicMock()

            result = await flow.async_step_user(
                user_input={
                    CONF_HOST: "bad-host",
                    CONF_PORT: DEFAULT_PORT,
                    CONF_TOKEN: "token",
                }
            )
            assert result["type"] == "form"
            assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_auth_error_shows_form(self, mock_api_client) -> None:
        """Test that auth failure re-shows form with error."""
        from custom_components.openclaw.api import AuthenticationError

        mock_api_client.list_models = AsyncMock(
            side_effect=AuthenticationError("Invalid token")
        )
        with patch(
            "custom_components.openclaw.config_flow.OpenClawApiClient",
            return_value=mock_api_client,
        ):
            flow = OpenClawConfigFlow()
            flow.hass = MagicMock()

            result = await flow.async_step_user(
                user_input={
                    CONF_HOST: "host",
                    CONF_PORT: DEFAULT_PORT,
                    CONF_TOKEN: "bad-token",
                }
            )
            assert result["type"] == "form"
            assert result["errors"]["base"] == "invalid_auth"

    @pytest.mark.asyncio
    async def test_unexpected_error_shows_unknown(self, mock_api_client) -> None:
        """Test that an unexpected exception maps to 'unknown' error."""
        mock_api_client.list_models = AsyncMock(side_effect=RuntimeError("Boom"))
        with patch(
            "custom_components.openclaw.config_flow.OpenClawApiClient",
            return_value=mock_api_client,
        ):
            flow = OpenClawConfigFlow()
            flow.hass = MagicMock()

            result = await flow.async_step_user(
                user_input={
                    CONF_HOST: "host",
                    CONF_PORT: DEFAULT_PORT,
                    CONF_TOKEN: "token",
                }
            )
            assert result["type"] == "form"
            assert result["errors"]["base"] == "unknown"


class TestHassioFlow:
    """Tests for Supervisor add-on discovery flow."""

    def _make_discovery(self, **overrides):
        from homeassistant.helpers.service_info.hassio import HassioServiceInfo
        defaults = dict(
            config={"host": "127.0.0.1", "port": DEFAULT_PORT, "token": "tok"},
            name="OpenClaw Gateway",
            slug="openclaw-gateway",
            uuid="aabbccdd-1234",
        )
        defaults.update(overrides)
        return HassioServiceInfo(**defaults)

    @pytest.mark.asyncio
    async def test_hassio_confirm_success(self, mock_api_client) -> None:
        """Discovery confirm creates entry on success."""
        with patch(
            "custom_components.openclaw.config_flow.OpenClawApiClient",
            return_value=mock_api_client,
        ):
            flow = OpenClawConfigFlow()
            flow.hass = MagicMock()

            disc = self._make_discovery()
            await flow.async_step_hassio(disc)

            result = await flow.async_step_hassio_confirm(user_input={})

            assert result["type"] == "create_entry"
            assert result["title"] == "OpenClaw Gateway"
            assert result["data"][CONF_HOST] == "127.0.0.1"
            assert result["data"][CONF_PORT] == DEFAULT_PORT
            assert result["data"][CONF_TOKEN] == "tok"

    @pytest.mark.asyncio
    async def test_hassio_confirm_shows_form_on_no_input(self, mock_api_client) -> None:
        """Discovery confirm shows form when user_input is None."""
        with patch(
            "custom_components.openclaw.config_flow.OpenClawApiClient",
            return_value=mock_api_client,
        ):
            flow = OpenClawConfigFlow()
            flow.hass = MagicMock()

            disc = self._make_discovery()
            await flow.async_step_hassio(disc)

            result = await flow.async_step_hassio_confirm(user_input=None)

            assert result["type"] == "form"
            assert result["step_id"] == "hassio_confirm"

    @pytest.mark.asyncio
    async def test_hassio_confirm_retries_on_connect_error(self, mock_api_client) -> None:
        """Discovery confirm shows error after connection failures."""
        mock_api_client.list_models = AsyncMock(
            side_effect=aiohttp.ClientError("refused")
        )
        with patch(
            "custom_components.openclaw.config_flow.OpenClawApiClient",
            return_value=mock_api_client,
        ), patch("asyncio.sleep", new_callable=AsyncMock):
            flow = OpenClawConfigFlow()
            flow.hass = MagicMock()

            disc = self._make_discovery()
            await flow.async_step_hassio(disc)

            result = await flow.async_step_hassio_confirm(user_input={})

            assert result["type"] == "form"
            assert result["errors"]["base"] == "cannot_connect"
            # list_models called 3 times (3 retry attempts)
            assert mock_api_client.list_models.call_count == 3


class TestReauthFlow:
    """Tests for token reauth flow."""

    @pytest.mark.asyncio
    async def test_reauth_confirm_success(self, mock_api_client) -> None:
        """Successful reauth updates token and aborts (reauth_successful)."""
        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_HOST: "10.0.0.1",
            CONF_PORT: DEFAULT_PORT,
            CONF_TOKEN: "old-token",
        }

        with patch(
            "custom_components.openclaw.config_flow.OpenClawApiClient",
            return_value=mock_api_client,
        ):
            flow = OpenClawConfigFlow()
            flow.hass = MagicMock()
            flow._get_reauth_entry = MagicMock(return_value=mock_entry)

            # Initiate reauth
            await flow.async_step_reauth({})

            # Supply new token
            result = await flow.async_step_reauth_confirm(
                user_input={CONF_TOKEN: "new-token"}
            )

            assert result["type"] == "abort"
            assert result["reason"] == "reauth_successful"

    @pytest.mark.asyncio
    async def test_reauth_confirm_invalid_token(self, mock_api_client) -> None:
        """Bad token during reauth shows form with invalid_auth error."""
        from custom_components.openclaw.api import AuthenticationError

        mock_api_client.list_models = AsyncMock(
            side_effect=AuthenticationError("bad token")
        )
        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_HOST: "10.0.0.1",
            CONF_PORT: DEFAULT_PORT,
            CONF_TOKEN: "old-token",
        }

        with patch(
            "custom_components.openclaw.config_flow.OpenClawApiClient",
            return_value=mock_api_client,
        ):
            flow = OpenClawConfigFlow()
            flow.hass = MagicMock()
            flow._get_reauth_entry = MagicMock(return_value=mock_entry)

            result = await flow.async_step_reauth_confirm(
                user_input={CONF_TOKEN: "still-bad"}
            )

            assert result["type"] == "form"
            assert result["errors"]["base"] == "invalid_auth"

    @pytest.mark.asyncio
    async def test_reauth_confirm_no_input_shows_form(self) -> None:
        """Reauth confirm with no input shows the form."""
        flow = OpenClawConfigFlow()
        flow.hass = MagicMock()

        result = await flow.async_step_reauth_confirm(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"


class TestOptionsFlow:
    """Tests for options flow."""

    @pytest.mark.asyncio
    async def test_options_init_shows_form(self) -> None:
        """Options init with no input shows the form."""
        flow = OpenClawOptionsFlow()

        result = await flow.async_step_init(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_init_saves_values(self) -> None:
        """Options init with valid input creates entry."""
        flow = OpenClawOptionsFlow()

        result = await flow.async_step_init(
            user_input={
                CONF_AGENT_ID: "butler",
                CONF_SESSION_MODE: SESSION_MODE_DEVICE,
            }
        )

        assert result["type"] == "create_entry"
        assert result["data"][CONF_AGENT_ID] == "butler"
        assert result["data"][CONF_SESSION_MODE] == SESSION_MODE_DEVICE
