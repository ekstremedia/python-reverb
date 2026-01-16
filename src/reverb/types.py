"""Type definitions for Python Reverb."""

from typing import Any, Awaitable, Callable, Protocol, TypeAlias

# Event handler that receives (event_name, data, channel_name)
EventHandler: TypeAlias = Callable[[str, Any, str | None], Awaitable[None]]

# Simpler handler that just receives data
SimpleEventHandler: TypeAlias = Callable[[Any], Awaitable[None]]

# Connection state callback
ConnectionCallback: TypeAlias = Callable[[], Awaitable[None]]

# Message callback (receives raw message dict)
MessageCallback: TypeAlias = Callable[[dict[str, Any]], Awaitable[None]]


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
