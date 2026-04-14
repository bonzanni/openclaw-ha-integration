"""Shared test fixtures for OpenClaw integration tests."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_stub_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


def _ensure_ha_stubs() -> None:
    """Create the minimal sys.modules stubs required by HA module imports.

    This runs before any test module is imported, so it must cover all
    homeassistant symbols used by any module under test.
    """
    if "homeassistant" in sys.modules:
        return  # real HA is installed — nothing to stub

    # homeassistant (top-level)
    ha = _make_stub_module("homeassistant")

    # homeassistant.core
    ha_core = _make_stub_module("homeassistant.core")
    ha_core.callback = lambda f: f
    ha_core.HomeAssistant = MagicMock

    # homeassistant.config_entries — full stubs including ConfigFlow/OptionsFlow
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

    # homeassistant.const
    ha_const = _make_stub_module("homeassistant.const")
    ha_const.Platform = MagicMock()
    ha_const.Platform.CONVERSATION = "conversation"
    ha_const.MATCH_ALL = "*"

    # homeassistant.exceptions
    ha_exc = _make_stub_module("homeassistant.exceptions")
    ha_exc.ConfigEntryAuthFailed = Exception
    ha_exc.ConfigEntryNotReady = Exception

    # homeassistant.helpers
    ha_helpers = _make_stub_module("homeassistant.helpers")

    # homeassistant.helpers.aiohttp_client
    ha_aiohttp = _make_stub_module("homeassistant.helpers.aiohttp_client")
    ha_aiohttp.async_get_clientsession = MagicMock(return_value=MagicMock())

    # homeassistant.helpers.service_info
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

    # homeassistant.helpers.device_registry
    ha_dr = _make_stub_module("homeassistant.helpers.device_registry")
    ha_dr.DeviceInfo = dict
    ha_dr.DeviceEntryType = MagicMock()
    ha_dr.DeviceEntryType.SERVICE = "service"

    # homeassistant.helpers.intent
    ha_intent = _make_stub_module("homeassistant.helpers.intent")

    # homeassistant.components
    ha_components = _make_stub_module("homeassistant.components")

    # homeassistant.components.conversation
    ha_conv = _make_stub_module("homeassistant.components.conversation")

    def _unique_id_property(self):
        return getattr(self, "_attr_unique_id", None)

    ha_conv.ConversationEntity = type("ConversationEntity", (), {
        "_attr_has_entity_name": False,
        "_attr_name": None,
        "_attr_unique_id": None,
        "unique_id": property(_unique_id_property),
    })
    ha_conv.ConversationInput = MagicMock
    ha_conv.ConversationResult = MagicMock
    ha_conv.ChatLog = MagicMock

    def mock_get_result(user_input, chat_log):
        return {"type": "result", "conversation_id": getattr(user_input, "conversation_id", None)}

    ha_conv.async_get_result_from_chat_log = mock_get_result

    # homeassistant.components.conversation.chat_log
    ha_conv_chatlog = _make_stub_module("homeassistant.components.conversation.chat_log")
    ha_conv_chatlog.ChatLog = ha_conv.ChatLog

    # Wire sub-modules onto their parents so attribute access works too
    ha.core = ha_core
    ha.config_entries = ha_ce
    ha.const = ha_const
    ha.exceptions = ha_exc
    ha.helpers = ha_helpers
    ha_helpers.aiohttp_client = ha_aiohttp
    ha_helpers.service_info = ha_si
    ha_si.hassio = ha_si_hassio
    ha_helpers.device_registry = ha_dr
    ha_helpers.intent = ha_intent
    ha.components = ha_components
    ha_components.conversation = ha_conv


_ensure_ha_stubs()

from custom_components.openclaw.api import OpenClawApiClient  # noqa: E402


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock aiohttp ClientSession."""
    return MagicMock()


@pytest.fixture
def api_client(mock_session: MagicMock) -> OpenClawApiClient:
    """Create an API client with mock session."""
    return OpenClawApiClient(
        session=mock_session,
        host="test-host",
        port=18789,
        token="test-token-abc123",
    )
