"""Tests for the ReverbClient class."""

from __future__ import annotations

import pytest

from reverb.client import ReverbClient
from reverb.config import ReverbConfig


class TestReverbClient:
    """Tests for the ReverbClient class."""

    def test_client_creation_with_config(self, config: ReverbConfig) -> None:
        """Test creating client with config object."""
        client = ReverbClient(config=config)

        assert client._config == config
        assert client.socket_id is None
        assert client.is_connected is False
        assert client.channels == {}

    def test_client_creation_with_params(self) -> None:
        """Test creating client with individual parameters."""
        client = ReverbClient(
            app_key="test-key",
            app_secret="test-secret",
            host="localhost",
            port=8080,
            scheme="ws",
        )

        assert client._config.app_key == "test-key"
        assert client._config.host == "localhost"
        assert client._config.port == 8080
        assert client._config.scheme == "ws"

    def test_global_handler_binding(self, config: ReverbConfig) -> None:
        """Test binding global event handlers."""
        client = ReverbClient(config=config)

        async def handler(event, data, channel):
            pass

        client.bind("test-event", handler)

        assert "test-event" in client._global_handlers
        assert handler in client._global_handlers["test-event"]

    def test_global_handler_unbinding(self, config: ReverbConfig) -> None:
        """Test unbinding global event handlers."""
        client = ReverbClient(config=config)

        async def handler(event, data, channel):
            pass

        client.bind("test-event", handler)
        client.unbind("test-event", handler)

        assert handler not in client._global_handlers.get("test-event", [])

    def test_global_handler_unbind_all(self, config: ReverbConfig) -> None:
        """Test unbinding all handlers for an event."""
        client = ReverbClient(config=config)

        async def handler1(event, data, channel):
            pass

        async def handler2(event, data, channel):
            pass

        client.bind("test-event", handler1)
        client.bind("test-event", handler2)
        client.unbind("test-event")

        assert "test-event" not in client._global_handlers


class TestReverbClientIntegration:
    """Integration tests that require a running Reverb server.

    These tests are skipped by default. To run them:
        REVERB_HOST=localhost REVERB_PORT=8080 pytest tests/test_client.py -k integration
    """

    @pytest.fixture
    def integration_config(self) -> ReverbConfig | None:
        """Create config from environment, or None if not configured."""
        import os

        if not os.environ.get("REVERB_HOST"):
            return None

        return ReverbConfig(
            app_key=os.environ.get("REVERB_APP_KEY", "test-key"),
            app_secret=os.environ.get("REVERB_APP_SECRET", "test-secret"),
            host=os.environ["REVERB_HOST"],
            port=int(os.environ.get("REVERB_PORT", "8080")),
            scheme=os.environ.get("REVERB_SCHEME", "ws"),  # type: ignore
        )

    @pytest.mark.asyncio
    async def test_integration_connect(self, integration_config: ReverbConfig | None) -> None:
        """Test connecting to a real Reverb server."""
        if integration_config is None:
            pytest.skip("REVERB_HOST not set")

        async with ReverbClient(config=integration_config) as client:
            assert client.is_connected
            assert client.socket_id is not None

    @pytest.mark.asyncio
    async def test_integration_subscribe(self, integration_config: ReverbConfig | None) -> None:
        """Test subscribing to a channel."""
        if integration_config is None:
            pytest.skip("REVERB_HOST not set")

        async with ReverbClient(config=integration_config) as client:
            channel = await client.subscribe("test-channel")

            assert channel.name == "test-channel"
            assert channel.is_subscribed
            assert "test-channel" in client.channels

    @pytest.mark.asyncio
    async def test_integration_event_handler(
        self, integration_config: ReverbConfig | None
    ) -> None:
        """Test receiving events."""
        if integration_config is None:
            pytest.skip("REVERB_HOST not set")

        import asyncio

        received_events: list[tuple] = []

        async def handler(event, data, channel):
            received_events.append((event, data, channel))

        async with ReverbClient(config=integration_config) as client:
            channel = await client.subscribe("test-channel")
            channel.bind("test-event", handler)

            # Wait briefly for any events
            await asyncio.sleep(0.5)

            # Note: This test passes if no errors occur during subscription
            # Actual event testing requires a server to broadcast events
            assert channel.is_subscribed
