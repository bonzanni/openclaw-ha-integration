"""OpenClaw Gateway API client."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from .const import TIMEOUT_CONNECT, TIMEOUT_HEALTH


class AuthenticationError(Exception):
    """Raised when gateway returns 401."""


class OpenClawApiClient:
    """Async client for OpenClaw Gateway HTTP API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        token: str,
    ) -> None:
        self._session = session
        self._base_url = f"http://{host}:{port}"
        self._token = token
        self._headers = {
            "Authorization": f"Bearer {token}",
            "x-openclaw-source": "homeassistant",
        }

    async def health_check(self) -> bool:
        """GET /healthz — check gateway is alive."""
        async with asyncio.timeout(TIMEOUT_HEALTH):
            resp = await self._session.get(
                f"{self._base_url}/healthz",
                headers=self._headers,
            )
            return resp.status == 200

    async def list_models(self) -> list[dict[str, Any]]:
        """GET /v1/models — discover available agents."""
        async with asyncio.timeout(TIMEOUT_HEALTH):
            resp = await self._session.get(
                f"{self._base_url}/v1/models",
                headers=self._headers,
            )
            if resp.status == 401:
                raise AuthenticationError("Invalid gateway token")
            resp.raise_for_status()
            data = await resp.json()
            return data.get("data", [])

    async def chat_completion_stream(
        self,
        messages: list[dict[str, str]],
        agent_id: str,
        session_key: str | None = None,
        channel: str = "voice",
    ) -> AsyncIterator[str]:
        """POST /v1/chat/completions with SSE streaming.

        Yields text chunks as they arrive from the gateway.
        """
        headers = {
            **self._headers,
            "Content-Type": "application/json",
            "x-openclaw-agent-id": agent_id,
            "x-openclaw-message-channel": channel,
            "x-openclaw-source": channel,
        }

        payload: dict[str, Any] = {
            "model": f"openclaw/{agent_id}",
            "messages": messages,
            "stream": True,
        }
        if session_key:
            payload["user"] = session_key

        resp = await self._session.post(
            f"{self._base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(connect=TIMEOUT_CONNECT),
        )
        if resp.status == 401:
            raise AuthenticationError("Invalid gateway token")
        resp.raise_for_status()

        async for line in resp.content:
            decoded = line.decode("utf-8").strip()
            if not decoded or not decoded.startswith("data: "):
                continue
            data_str = decoded[6:]
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content")
            if content:
                yield content
