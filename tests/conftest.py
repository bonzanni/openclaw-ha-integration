"""Shared test fixtures for OpenClaw integration tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.openclaw.api import OpenClawApiClient


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
