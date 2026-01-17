"""Integration tests for the health check flow.

These tests require:
1. A running Reverb server
2. The Laravel API endpoints for device ping/pong

Run with:
    REVERB_HOST=ekstremedia.no pytest tests/test_integration.py -v
"""

from __future__ import annotations

import asyncio
import os

import pytest


def has_reverb_config() -> bool:
    """Check if Reverb configuration is available."""
    return bool(os.environ.get("REVERB_HOST"))


@pytest.mark.skipif(not has_reverb_config(), reason="REVERB_HOST not set")
class TestHealthCheckIntegration:
    """Integration tests for the health check system."""

    @pytest.fixture
    def api_base_url(self) -> str:
        """Get API base URL from environment."""
        return os.environ.get("API_BASE_URL", "https://ekstremedia.no")

    @pytest.mark.asyncio
    async def test_connect_to_reverb(self) -> None:
        """Test connecting to the Reverb server."""
        from reverb import ReverbClient

        async with ReverbClient() as client:
            assert client.is_connected
            assert client.socket_id is not None
            assert client.socket_id.count(".") == 1  # Format: xxx.yyy

    @pytest.mark.asyncio
    async def test_subscribe_to_device_channel(self) -> None:
        """Test subscribing to a device channel."""
        from reverb import ReverbClient

        device_id = "test-device"

        async with ReverbClient() as client:
            channel = await client.subscribe(f"device.{device_id}")

            assert channel.name == f"device.{device_id}"
            assert channel.is_subscribed

    @pytest.mark.asyncio
    async def test_receive_health_ping(self, api_base_url: str) -> None:
        """Test receiving a health ping event."""
        import aiohttp

        from reverb import ReverbClient

        device_id = "integration-test"
        received_pings: list[dict] = []

        async def on_ping(event, data, channel):
            received_pings.append(data)

        async with ReverbClient() as client:
            channel = await client.subscribe(f"device.{device_id}")
            channel.bind("health.ping", on_ping)

            # Give time for subscription to complete
            await asyncio.sleep(0.5)

            # Send a ping via HTTP
            async with aiohttp.ClientSession() as session:
                url = f"{api_base_url}/api/device/{device_id}/ping"
                async with session.post(url) as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    request_id = data.get("request_id")

            # Wait for the ping to arrive
            await asyncio.sleep(1.0)

            # Verify we received the ping
            assert len(received_pings) == 1
            assert received_pings[0].get("request_id") == request_id
            assert received_pings[0].get("device_id") == device_id

    @pytest.mark.asyncio
    async def test_full_health_check_flow(self, api_base_url: str) -> None:
        """Test the complete health check ping/pong flow."""
        import aiohttp

        from reverb import ReverbClient

        device_id = "integration-test-full"
        ping_received = asyncio.Event()
        received_request_id: str | None = None

        async def on_ping(event, data, channel):
            nonlocal received_request_id
            received_request_id = data.get("request_id")

            # Send pong response
            async with aiohttp.ClientSession() as session:
                url = f"{api_base_url}/api/device/pong"
                payload = {
                    "device_id": device_id,
                    "request_id": received_request_id,
                    "status": "healthy",
                    "metrics": {"test": True},
                }
                async with session.post(url, json=payload) as resp:
                    assert resp.status == 200

            ping_received.set()

        async with ReverbClient() as client:
            channel = await client.subscribe(f"device.{device_id}")
            channel.bind("health.ping", on_ping)

            await asyncio.sleep(0.5)

            # Send ping
            async with aiohttp.ClientSession() as session:
                url = f"{api_base_url}/api/device/{device_id}/ping"
                async with session.post(url) as resp:
                    assert resp.status == 200

            # Wait for ping to be received and processed
            try:
                await asyncio.wait_for(ping_received.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                pytest.fail("Timeout waiting for ping event")

            assert received_request_id is not None


@pytest.mark.skipif(not has_reverb_config(), reason="REVERB_HOST not set")
class TestReconnection:
    """Tests for reconnection behavior."""

    @pytest.mark.asyncio
    async def test_reconnect_on_disconnect(self) -> None:
        """Test that client reconnects after disconnection."""
        from reverb import ReverbClient

        async with ReverbClient() as client:
            assert client.socket_id is not None
            assert client.is_connected

            # Force disconnect by closing websocket
            if client._connection._ws:
                await client._connection._ws.close()

            # Wait for reconnection
            await asyncio.sleep(3.0)

            # Should have reconnected with new socket_id
            assert client.is_connected
            # Note: socket_id may or may not change depending on server
