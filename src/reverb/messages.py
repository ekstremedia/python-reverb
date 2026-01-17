"""Message parsing and construction for Pusher protocol."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class Events:
    """Pusher protocol event names."""

    # Connection events
    CONNECTION_ESTABLISHED = "pusher:connection_established"
    ERROR = "pusher:error"

    # Subscription events
    SUBSCRIBE = "pusher:subscribe"
    UNSUBSCRIBE = "pusher:unsubscribe"
    SUBSCRIPTION_SUCCEEDED = "pusher_internal:subscription_succeeded"
    SUBSCRIPTION_ERROR = "pusher:subscription_error"

    # Presence events
    MEMBER_ADDED = "pusher_internal:member_added"
    MEMBER_REMOVED = "pusher_internal:member_removed"

    # Keepalive events
    PING = "pusher:ping"
    PONG = "pusher:pong"

    # User authentication
    SIGNIN = "pusher:signin"


@dataclass
class Message:
    """Base message structure for Pusher protocol."""

    event: str
    data: Any = field(default_factory=dict)
    channel: str | None = None

    @classmethod
    def from_json(cls, raw: str) -> "Message":
        """Parse JSON message from server."""
        parsed = json.loads(raw)
        event = parsed.get("event", "")
        channel = parsed.get("channel")

        # Data may be double-encoded JSON string
        data = parsed.get("data", {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                pass  # Keep as string if not valid JSON

        return cls(event=event, data=data, channel=channel)

    def to_json(self) -> str:
        """Serialize to JSON for sending."""
        msg: dict[str, Any] = {"event": self.event}

        if self.channel:
            msg["channel"] = self.channel

        # Data should be JSON-encoded string for protocol compliance
        if isinstance(self.data, (dict, list)):
            msg["data"] = json.dumps(self.data)
        else:
            msg["data"] = self.data

        return json.dumps(msg)


class Messages:
    """Factory for creating protocol messages."""

    @staticmethod
    def subscribe(
        channel: str,
        auth: str | None = None,
        channel_data: str | None = None,
    ) -> Message:
        """Create subscription message."""
        data: dict[str, Any] = {"channel": channel}
        if auth:
            data["auth"] = auth
        if channel_data:
            data["channel_data"] = channel_data
        return Message(event=Events.SUBSCRIBE, data=data)

    @staticmethod
    def unsubscribe(channel: str) -> Message:
        """Create unsubscription message."""
        return Message(event=Events.UNSUBSCRIBE, data={"channel": channel})

    @staticmethod
    def pong() -> Message:
        """Create pong message."""
        return Message(event=Events.PONG, data={})

    @staticmethod
    def client_event(channel: str, event: str, data: Any) -> Message:
        """Create a client event message (client-* events)."""
        return Message(event=f"client-{event}", data=data, channel=channel)
