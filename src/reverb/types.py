"""Type definitions for Python Reverb."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, Protocol

# Event handler that receives (event_name, data, channel_name)
EventHandler = Callable[[str, Any, Optional[str]], Awaitable[None]]

# Simpler handler that just receives data
SimpleEventHandler = Callable[[Any], Awaitable[None]]

# Connection state callback
ConnectionCallback = Callable[[], Awaitable[None]]

# Message callback (receives raw message dict)
MessageCallback = Callable[[Dict[str, Any]], Awaitable[None]]


class ChannelProtocol(Protocol):
    """Protocol for channel implementations."""

    @property
    def name(self) -> str:
        """Channel name."""
        ...

    @property
    def is_subscribed(self) -> bool:
        """Whether currently subscribed."""
        ...

    def bind(self, event: str, handler: EventHandler) -> "ChannelProtocol":
        """Bind an event handler."""
        ...

    def unbind(self, event: str, handler: EventHandler | None = None) -> "ChannelProtocol":
        """Remove event handler(s)."""
        ...
