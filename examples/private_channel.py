#!/usr/bin/env python3
"""
Private channel example for Python Reverb.

This example shows how to connect to a private channel with HMAC authentication.

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


async def handle_direct_message(event: str, data: Any, channel: str | None) -> None:
    """Handle incoming direct messages."""
    sender = data.get("from")
    message = data.get("message")
    print(f"DM from {sender}: {message}")


async def main() -> None:
    """Main entry point."""
    user_id = "123"  # Your user ID

    async with ReverbClient() as client:
        print(f"Connected! Socket ID: {client.socket_id}")

        # Subscribe to a private channel (note the 'private-' prefix)
        # The library automatically handles HMAC authentication
        private_channel = await client.subscribe(f"private-user.{user_id}")

        # Bind event handlers
        private_channel.bind("direct-message", handle_direct_message)
        private_channel.bind("notification", handle_direct_message)

        # You can also send client events on private channels
        # Note: Your Reverb server must be configured to allow client events
        # await private_channel.trigger("typing", {"typing": True})

        print(f"Subscribed to private channel for user {user_id}")
        print("Listening for events... Press Ctrl+C to stop.")

        await client.listen()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
