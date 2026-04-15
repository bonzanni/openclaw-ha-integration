"""OpenClaw conversation entity for Home Assistant Assist pipeline."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any, Literal

import aiohttp

from homeassistant.components import conversation
from homeassistant.components.conversation import ChatLog
from homeassistant.const import MATCH_ALL
from homeassistant.helpers import intent

from .api import AuthenticationError, OpenClawApiClient
from .const import (
    CONF_AGENT_ID,
    CONF_SESSION_MODE,
    DEFAULT_AGENT_ID,
    DEFAULT_SESSION_MODE,
    DOMAIN,
    ERROR_AUTH,
    ERROR_CONNECTION,
    ERROR_TIMEOUT,
    SESSION_MODE_CONVERSATION,
    SESSION_MODE_DEVICE,
    SESSION_MODE_USER,
    TIMEOUT_TOTAL,
)

_LOGGER = logging.getLogger(__name__)

from homeassistant.config_entries import ConfigEntry

OpenClawConfigEntry = ConfigEntry  # type: ignore[type-arg]


async def async_setup_entry(
    hass: Any,
    entry: OpenClawConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up OpenClaw conversation entity from a config entry."""
    async_add_entities([OpenClawConversationEntity(entry)])


class OpenClawConversationEntity(conversation.ConversationEntity):
    """OpenClaw agent as HA conversation entity."""

    _attr_has_entity_name = True
    _attr_name = "OpenClaw"

    def __init__(self, entry: OpenClawConfigEntry) -> None:
        """Initialize the conversation entity."""
        self.entry = entry
        self._client: OpenClawApiClient = entry.runtime_data
        self._agent_id = entry.options.get(CONF_AGENT_ID, DEFAULT_AGENT_ID)
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return supported languages — OpenClaw agents handle any language."""
        return MATCH_ALL

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: ChatLog,
    ) -> conversation.ConversationResult:
        """Process voice/text input through OpenClaw agent."""
        session_key = self._build_session_key(user_input)
        channel = "voice"

        try:
            async with asyncio.timeout(TIMEOUT_TOTAL):
                stream = self._client.chat_completion_stream(
                    messages=[{"role": "user", "content": user_input.text}],
                    agent_id=self._agent_id,
                    session_key=session_key,
                    channel=channel,
                )
                async for _content in chat_log.async_add_delta_content_stream(
                    user_input.agent_id,
                    self._to_deltas(stream),
                ):
                    pass
        except asyncio.TimeoutError:
            return self._error_result(user_input, ERROR_TIMEOUT)
        except AuthenticationError:
            self.entry.async_start_reauth(self.hass)
            return self._error_result(user_input, ERROR_AUTH)
        except (aiohttp.ClientError, aiohttp.ServerDisconnectedError):
            return self._error_result(user_input, ERROR_CONNECTION)

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    def _build_session_key(
        self, user_input: conversation.ConversationInput
    ) -> str:
        """Build OpenClaw session key for persistent context.

        Format: ha:<channel>:<agent_id>:<scope_id>
        Fallback chain: device_id -> user_id -> conversation_id
        """
        channel = "voice"
        session_mode = self.entry.options.get(
            CONF_SESSION_MODE, DEFAULT_SESSION_MODE
        )

        if session_mode == SESSION_MODE_DEVICE and user_input.device_id:
            scope_id = user_input.device_id
        elif (
            session_mode == SESSION_MODE_USER
            and user_input.context
            and user_input.context.user_id
        ):
            scope_id = user_input.context.user_id
        elif session_mode == SESSION_MODE_CONVERSATION:
            scope_id = user_input.conversation_id
        elif user_input.device_id:
            scope_id = user_input.device_id
        elif user_input.context and user_input.context.user_id:
            scope_id = user_input.context.user_id
        else:
            scope_id = user_input.conversation_id

        return f"ha:{channel}:{self._agent_id}:{scope_id}"

    @staticmethod
    async def _to_deltas(
        stream: AsyncIterator[str],
    ) -> AsyncIterator[dict]:
        """Transform SSE text chunks into ChatLog delta dicts."""
        first = True
        async for chunk in stream:
            delta: dict = {"content": chunk}
            if first:
                delta["role"] = "assistant"
                first = False
            yield delta

    @staticmethod
    def _error_result(
        user_input: conversation.ConversationInput,
        message: str,
    ) -> conversation.ConversationResult:
        """Build an error ConversationResult with a speech fallback."""
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_error(
            intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
            message,
        )
        return conversation.ConversationResult(
            response=response,
            conversation_id=user_input.conversation_id,
        )
