"""Tests for OpenClaw API client."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.openclaw.api import (
    AuthenticationError,
    OpenClawApiClient,
)


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock aiohttp ClientSession."""
    return MagicMock()


@pytest.fixture
def client(mock_session: MagicMock) -> OpenClawApiClient:
    """Create an API client with mock session."""
    return OpenClawApiClient(
        session=mock_session,
        host="test-host",
        port=18789,
        token="test-token",
    )


class TestHealthCheck:
    """Tests for health_check method."""

    @pytest.mark.asyncio
    async def test_healthy(self, client: OpenClawApiClient, mock_session: MagicMock) -> None:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_session.get = AsyncMock(return_value=mock_resp)

        result = await client.health_check()

        assert result is True
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        assert "healthz" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_unhealthy(self, client: OpenClawApiClient, mock_session: MagicMock) -> None:
        mock_resp = AsyncMock()
        mock_resp.status = 503
        mock_session.get = AsyncMock(return_value=mock_resp)

        result = await client.health_check()

        assert result is False


class TestListModels:
    """Tests for list_models method."""

    @pytest.mark.asyncio
    async def test_returns_models(self, client: OpenClawApiClient, mock_session: MagicMock) -> None:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "data": [
                {"id": "openclaw/default", "object": "model"},
                {"id": "openclaw/butler", "object": "model"},
            ]
        })
        mock_resp.raise_for_status = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_resp)

        result = await client.list_models()

        assert len(result) == 2
        assert result[0]["id"] == "openclaw/default"

    @pytest.mark.asyncio
    async def test_auth_failure_raises(self, client: OpenClawApiClient, mock_session: MagicMock) -> None:
        mock_resp = AsyncMock()
        mock_resp.status = 401
        mock_session.get = AsyncMock(return_value=mock_resp)

        with pytest.raises(AuthenticationError):
            await client.list_models()


class TestChatCompletionStream:
    """Tests for chat_completion_stream method."""

    @pytest.mark.asyncio
    async def test_parses_sse_chunks(self, client: OpenClawApiClient, mock_session: MagicMock) -> None:
        sse_lines = [
            b'data: {"choices":[{"delta":{"role":"assistant","content":"Hello"}}]}\n',
            b"\n",
            b'data: {"choices":[{"delta":{"content":" world"}}]}\n',
            b"\n",
            b"data: [DONE]\n",
            b"\n",
        ]

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.content = AsyncIteratorMock(sse_lines)
        mock_session.post = AsyncMock(return_value=mock_resp)

        chunks = []
        async for chunk in client.chat_completion_stream(
            messages=[{"role": "user", "content": "hi"}],
            agent_id="default",
            session_key="ha:voice:default:device-1",
        ):
            chunks.append(chunk)

        assert chunks == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_auth_failure_raises(self, client: OpenClawApiClient, mock_session: MagicMock) -> None:
        mock_resp = AsyncMock()
        mock_resp.status = 401
        mock_session.post = AsyncMock(return_value=mock_resp)

        with pytest.raises(AuthenticationError):
            async for _ in client.chat_completion_stream(
                messages=[{"role": "user", "content": "hi"}],
                agent_id="default",
            ):
                pass

    @pytest.mark.asyncio
    async def test_sends_routing_headers_and_user(self, client: OpenClawApiClient, mock_session: MagicMock) -> None:
        sse_lines = [b"data: [DONE]\n", b"\n"]
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.content = AsyncIteratorMock(sse_lines)
        mock_session.post = AsyncMock(return_value=mock_resp)

        async for _ in client.chat_completion_stream(
            messages=[{"role": "user", "content": "hi"}],
            agent_id="butler",
            session_key="ha:voice:butler:kitchen-01",
            channel="voice",
        ):
            pass

        call_kwargs = mock_session.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
        assert headers["x-openclaw-agent-id"] == "butler"
        assert headers["x-openclaw-message-channel"] == "voice"
        assert headers["x-openclaw-source"] == "voice"
        assert "x-openclaw-session-key" not in headers

        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json", {})
        assert body["user"] == "ha:voice:butler:kitchen-01"
        assert body["model"] == "openclaw/butler"

    @pytest.mark.asyncio
    async def test_skips_empty_content(self, client: OpenClawApiClient, mock_session: MagicMock) -> None:
        sse_lines = [
            b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n',
            b"\n",
            b'data: {"choices":[{"delta":{"content":"ok"}}]}\n',
            b"\n",
            b"data: [DONE]\n",
            b"\n",
        ]
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.content = AsyncIteratorMock(sse_lines)
        mock_session.post = AsyncMock(return_value=mock_resp)

        chunks = []
        async for chunk in client.chat_completion_stream(
            messages=[{"role": "user", "content": "hi"}],
            agent_id="default",
        ):
            chunks.append(chunk)

        assert chunks == ["ok"]


class AsyncIteratorMock:
    """Mock for aiohttp response content (async iterator of bytes)."""

    def __init__(self, items: list[bytes]) -> None:
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration
