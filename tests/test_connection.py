"""Tests for WebSocket connection management."""

from __future__ import annotations

import pytest

from reverb.config import ReverbConfig
from reverb.connection import Connection
from reverb.messages import Message


class TestConnection:
    """Tests for the Connection class."""

    def test_build_url(self, config: ReverbConfig) -> None:
        """Test WebSocket URL construction."""
        url = config.build_url()

        assert url.startswith("ws://localhost:8080/app/test-key")
        assert "protocol=7" in url
        assert "client=python-reverb" in url
        assert "version=" in url

    def test_build_url_with_wss(self) -> None:
        """Test WebSocket URL with TLS."""
        config = ReverbConfig(
            app_key="key",
            app_secret="secret",
            host="example.com",
            scheme="wss",
            port=443,
        )

        url = config.build_url()

        assert url.startswith("wss://example.com:443/app/key")

    def test_initial_state(self, config: ReverbConfig) -> None:
        """Test connection initial state."""

        async def noop_message(msg: Message) -> None:
            pass

        async def noop_connect(socket_id: str) -> None:
            pass

        async def noop() -> None:
            pass

        async def noop_error(e: Exception) -> None:
            pass

        conn = Connection(
            config=config,
            on_message=noop_message,
            on_connect=noop_connect,
            on_disconnect=noop,
            on_error=noop_error,
        )

        assert conn.socket_id is None
        assert conn.is_connected is False

    def test_backoff_calculation(self, config: ReverbConfig) -> None:
        """Test exponential backoff delay calculation."""

        async def noop_message(msg: Message) -> None:
            pass

        async def noop_connect(socket_id: str) -> None:
            pass

        async def noop() -> None:
            pass

        async def noop_error(e: Exception) -> None:
            pass

        conn = Connection(
            config=config,
            on_message=noop_message,
            on_connect=noop_connect,
            on_disconnect=noop,
            on_error=noop_error,
        )

        # First attempt
        conn._reconnect_attempts = 1
        delay1 = conn._calculate_backoff_delay()
        assert config.reconnect_delay_min <= delay1 <= config.reconnect_delay_min * 1.25

        # Second attempt (should be ~2x)
        conn._reconnect_attempts = 2
        delay2 = conn._calculate_backoff_delay()
        assert delay2 > delay1

        # Many attempts should be capped at max
        conn._reconnect_attempts = 100
        delay_max = conn._calculate_backoff_delay()
        assert delay_max <= config.reconnect_delay_max * 1.25
