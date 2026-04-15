"""Tests for OpenClaw conversation entity."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Stub HA modules before importing conversation.py
def _ensure_ha_stubs():
    """Create minimal HA module stubs if homeassistant is not installed."""
    if "homeassistant" in sys.modules:
        return

    # Core stubs
    ha = MagicMock()
    ha.const.MATCH_ALL = "*"
    ha.const.Platform.CONVERSATION = "conversation"
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.const"] = ha.const
    sys.modules["homeassistant.core"] = MagicMock()
    sys.modules["homeassistant.config_entries"] = MagicMock()

    # Conversation stubs
    conv = MagicMock()
    def _unique_id_property(self):
        return getattr(self, "_attr_unique_id", None)

    conv.ConversationEntity = type("ConversationEntity", (), {
        "_attr_has_entity_name": False,
        "_attr_name": None,
        "_attr_unique_id": None,
        "unique_id": property(_unique_id_property),
    })
    conv.ConversationInput = MagicMock
    conv.ConversationResult = MagicMock
    conv.ChatLog = MagicMock

    def mock_get_result(user_input, chat_log):
        return {"type": "result", "conversation_id": getattr(user_input, "conversation_id", None)}

    conv.async_get_result_from_chat_log = mock_get_result
    sys.modules["homeassistant.components"] = MagicMock()
    sys.modules["homeassistant.components.conversation"] = conv
    sys.modules["homeassistant.components.conversation.chat_log"] = MagicMock()
    sys.modules["homeassistant.components.conversation.chat_log"].ChatLog = conv.ChatLog

    # Device registry / intent stubs
    dr = MagicMock()
    dr.DeviceInfo = dict
    dr.DeviceEntryType = MagicMock()
    dr.DeviceEntryType.SERVICE = "service"
    sys.modules["homeassistant.helpers"] = MagicMock()
    sys.modules["homeassistant.helpers.device_registry"] = dr
    intent_mod = MagicMock()
    sys.modules["homeassistant.helpers.intent"] = intent_mod

_ensure_ha_stubs()

from custom_components.openclaw.const import (
    CONF_AGENT_ID,
    CONF_SESSION_MODE,
    DEFAULT_AGENT_ID,
    DOMAIN,
    SESSION_MODE_CONVERSATION,
    SESSION_MODE_DEVICE,
    SESSION_MODE_USER,
)
from custom_components.openclaw.conversation import OpenClawConversationEntity


def _make_entity(
    agent_id: str = DEFAULT_AGENT_ID,
    session_mode: str = SESSION_MODE_DEVICE,
) -> OpenClawConversationEntity:
    """Create entity with mocked config entry."""
    mock_entry = MagicMock()
    mock_entry.entry_id = "test-entry-123"
    mock_entry.options = {
        CONF_AGENT_ID: agent_id,
        CONF_SESSION_MODE: session_mode,
    }
    mock_entry.runtime_data = AsyncMock()
    mock_entry.runtime_data.chat_completion_stream = AsyncMock()

    entity = OpenClawConversationEntity(mock_entry)
    return entity


def _make_user_input(
    text: str = "turn on the lights",
    device_id: str | None = "kitchen-satellite-01",
    user_id: str | None = "user-abc",
    conversation_id: str | None = "conv-xyz",
    language: str = "en",
    agent_id: str = "conversation.openclaw",
) -> MagicMock:
    """Create a mock ConversationInput."""
    mock = MagicMock()
    mock.text = text
    mock.device_id = device_id
    mock.language = language
    mock.agent_id = agent_id
    mock.conversation_id = conversation_id
    mock.context = MagicMock()
    mock.context.user_id = user_id
    return mock


class TestSessionKeyBuilding:
    """Tests for _build_session_key method."""

    def test_device_mode_with_device_id(self) -> None:
        entity = _make_entity(agent_id="butler", session_mode=SESSION_MODE_DEVICE)
        user_input = _make_user_input(device_id="kitchen-01")

        key = entity._build_session_key(user_input)

        assert key == "ha:voice:butler:kitchen-01"

    def test_device_mode_falls_back_to_user_id(self) -> None:
        entity = _make_entity(agent_id="butler", session_mode=SESSION_MODE_DEVICE)
        user_input = _make_user_input(device_id=None, user_id="user-abc")

        key = entity._build_session_key(user_input)

        assert key == "ha:voice:butler:user-abc"

    def test_device_mode_falls_back_to_conversation_id(self) -> None:
        entity = _make_entity(agent_id="butler", session_mode=SESSION_MODE_DEVICE)
        user_input = _make_user_input(device_id=None, user_id=None)

        key = entity._build_session_key(user_input)

        assert key == "ha:voice:butler:conv-xyz"

    def test_user_mode_with_user_id(self) -> None:
        entity = _make_entity(agent_id="main", session_mode=SESSION_MODE_USER)
        user_input = _make_user_input(device_id="device-1", user_id="user-abc")

        key = entity._build_session_key(user_input)

        assert key == "ha:voice:main:user-abc"

    def test_user_mode_falls_back_to_device_id(self) -> None:
        entity = _make_entity(agent_id="main", session_mode=SESSION_MODE_USER)
        user_input = _make_user_input(device_id="device-1", user_id=None)

        key = entity._build_session_key(user_input)

        assert key == "ha:voice:main:device-1"

    def test_conversation_mode(self) -> None:
        entity = _make_entity(
            agent_id="butler", session_mode=SESSION_MODE_CONVERSATION
        )
        user_input = _make_user_input(conversation_id="conv-123")

        key = entity._build_session_key(user_input)

        assert key == "ha:voice:butler:conv-123"


class TestEntityProperties:
    """Tests for entity attributes."""

    def test_unique_id(self) -> None:
        entity = _make_entity()
        assert entity.unique_id == "test-entry-123"

    def test_supported_languages_is_match_all(self) -> None:
        entity = _make_entity()
        assert entity.supported_languages == "*"

    def test_name(self) -> None:
        entity = _make_entity()
        assert entity._attr_name == "OpenClaw"
        assert entity._attr_has_entity_name is False

    def test_device_info(self) -> None:
        entity = _make_entity()
        info = entity.device_info
        assert (DOMAIN, "test-entry-123") in info["identifiers"]
        assert info["manufacturer"] == "OpenClaw"
        assert info["model"] == "Conversation Agent (main)"
        assert "sw_version" in info
