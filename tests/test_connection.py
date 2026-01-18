"""Tests for WebSocket connection management."""

from __future__ import annotations

from unittest.mock import MagicMock

from reverb.config import ReverbConfig
from reverb.connection import Connection
from reverb.messages import Message


def _create_connection(config: ReverbConfig) -> Connection:
    """Helper to create a Connection with noop callbacks."""

    async def noop_message(msg: Message) -> None:
        pass

    async def noop_connect(socket_id: str) -> None:
        pass

    async def noop() -> None:
        pass

    async def noop_error(e: Exception) -> None:
        pass

    return Connection(
        config=config,
        on_message=noop_message,
        on_connect=noop_connect,
        on_disconnect=noop,
        on_error=noop_error,
    )


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
        conn = _create_connection(config)

        assert conn.socket_id is None
        assert conn.is_connected is False

    def test_is_connected_requires_connected_flag(self, config: ReverbConfig) -> None:
        """Test is_connected returns False when _connected is False."""
        conn = _create_connection(config)

        # Even with a mock websocket, should return False if _connected is False
        conn._ws = MagicMock()
        conn._connected = False

        assert conn.is_connected is False

    def test_is_connected_requires_websocket(self, config: ReverbConfig) -> None:
        """Test is_connected returns False when websocket is None."""
        conn = _create_connection(config)

        conn._connected = True
        conn._ws = None

        assert conn.is_connected is False

    def test_is_connected_checks_websocket_state(self, config: ReverbConfig) -> None:
        """Test is_connected checks the actual websocket state."""
        conn = _create_connection(config)

        mock_ws = MagicMock()
        conn._ws = mock_ws
        conn._connected = True

        # When websocket state is OPEN, should return True
        mock_ws.state.name = "OPEN"
        assert conn.is_connected is True

        # When websocket state is CLOSED, should return False
        mock_ws.state.name = "CLOSED"
        assert conn.is_connected is False

        # When websocket state is CLOSING, should return False
        mock_ws.state.name = "CLOSING"
        assert conn.is_connected is False

    def test_is_connected_handles_state_error(self, config: ReverbConfig) -> None:
        """Test is_connected returns False if checking state raises an error."""
        conn = _create_connection(config)

        mock_ws = MagicMock()
        mock_ws.state.name = property(lambda self: (_ for _ in ()).throw(AttributeError()))
        # Make accessing state.name raise an exception
        type(mock_ws.state).name = property(lambda self: (_ for _ in ()).throw(AttributeError("no state")))

        conn._ws = mock_ws
        conn._connected = True

        # Should return False gracefully when state check fails
        assert conn.is_connected is False

    def test_backoff_calculation(self, config: ReverbConfig) -> None:
        """Test exponential backoff delay calculation."""
        conn = _create_connection(config)

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
