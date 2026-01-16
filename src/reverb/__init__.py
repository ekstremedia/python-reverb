"""
Python Reverb - Async client for Laravel Reverb WebSocket servers.

Example:
    from reverb import ReverbClient

    async def main():
        async with ReverbClient() as client:
            channel = await client.subscribe("my-channel")
            channel.bind("my-event", handle_event)
            await client.listen()
"""

from reverb.channels import Channel, PresenceChannel, PrivateChannel, PublicChannel
from reverb.client import ReverbClient
from reverb.config import ReverbConfig
from reverb.exceptions import (
    AuthenticationError,
    ConnectionError,
    ProtocolError,
    ReverbError,
    SubscriptionError,
    TimeoutError,
)
from reverb.messages import Events, Message
from reverb.types import EventHandler, SimpleEventHandler

__version__ = "0.1.0"

__all__ = [
    # Main client
    "ReverbClient",
    "ReverbConfig",
    # Channels
    "Channel",
    "PublicChannel",
    "PrivateChannel",
    "PresenceChannel",
    # Messages
    "Message",
    "Events",
    # Exceptions
    "ReverbError",
    "ConnectionError",
    "AuthenticationError",
    "SubscriptionError",
    "ProtocolError",
    "TimeoutError",
    # Types
    "EventHandler",
    "SimpleEventHandler",
]
