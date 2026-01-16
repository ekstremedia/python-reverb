#!/usr/bin/env python3
"""
Basic usage example for Python Reverb.

This example shows how to connect to a Reverb server, subscribe to a channel,
and handle events.

Environment variables required:
    REVERB_APP_KEY: Your Reverb application key
    REVERB_APP_SECRET: Your Reverb application secret
    REVERB_HOST: Reverb server hostname
"""

import asyncio
import logging
from typing import Any

from reverb import ReverbClient

logging.basicConfig(level=logging.INFO)


async def handle_message(event: str, data: Any, channel: str | None) -> None:
    """Handle incoming messages."""
    print(f"Received event '{event}' on channel '{channel}':")
    print(f"  Data: {data}")


async def main() -> None:
    """Main entry point."""
    # Create client - configuration is loaded from environment variables
    async with ReverbClient() as client:
        print(f"Connected! Socket ID: {client.socket_id}")

        # Subscribe to a public channel
        channel = await client.subscribe("notifications")

        # Bind event handlers
        channel.bind("new-notification", handle_message)
        channel.bind("alert", handle_message)

        # You can also bind to all events using '*'
        # channel.bind("*", handle_message)

        print("Listening for events... Press Ctrl+C to stop.")

        # Listen for events (blocks until disconnected)
        await client.listen()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
