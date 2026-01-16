"""Channel abstractions for public, private, and presence channels."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from .auth import Authenticator
from .messages import Events, Message, Messages
from .types import EventHandler

if TYPE_CHECKING:
    from .client import ReverbClient

logger = logging.getLogger(__name__)


class Channel(ABC):
    """Base class for all channel types."""

    def __init__(self, name: str, client: ReverbClient) -> None:
        self._name = name
        self._client = client
        self._subscribed = False
        self._handlers: dict[str, list[EventHandler]] = {}

    @property
    def name(self) -> str:
        """Channel name."""
        return self._name

    @property
    def is_subscribed(self) -> bool:
        """Whether currently subscribed."""
        return self._subscribed

    def bind(self, event: str, handler: EventHandler) -> Channel:
        """
        Bind an event handler. Returns self for chaining.

        Args:
            event: Event name to listen for
            handler: Async function(event, data, channel) to call
        """
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
        logger.debug(f"Bound handler for '{event}' on channel '{self._name}'")
        return self

    def unbind(self, event: str, handler: EventHandler | None = None) -> Channel:
        """
        Remove event handler(s). Returns self for chaining.

        Args:
            event: Event name
            handler: Specific handler to remove, or None to remove all
        """
        if event in self._handlers:
            if handler is None:
                del self._handlers[event]
            else:
                self._handlers[event] = [h for h in self._handlers[event] if h != handler]
        return self

    async def _handle_event(self, event: str, data: Any) -> None:
        """Dispatch event to registered handlers."""
        handlers = self._handlers.get(event, []) + self._handlers.get("*", [])

        for handler in handlers:
            try:
                await handler(event, data, self._name)
            except Exception as e:
                logger.error(f"Handler error for '{event}' on '{self._name}': {e}")

    async def trigger(self, event: str, data: Any) -> None:
        """
        Trigger a client event on this channel.

        Note: Client events must be prefixed with 'client-' by the protocol.
        This method adds the prefix automatically if not present.

        Args:
            event: Event name (will be prefixed with 'client-' if needed)
            data: Event data to send
        """
        if not self._subscribed:
            raise RuntimeError(f"Cannot trigger event on unsubscribed channel '{self._name}'")

        # Ensure client- prefix
        if not event.startswith("client-"):
            event = f"client-{event}"

        message = Message(event=event, data=data, channel=self._name)
        await self._client._connection.send(message)
        logger.debug(f"Triggered '{event}' on channel '{self._name}'")

    @abstractmethod
    async def _subscribe(self) -> None:
        """Internal subscription logic."""
        pass

    async def _unsubscribe(self) -> None:
        """Unsubscribe from channel."""
        if not self._subscribed:
            return

        message = Messages.unsubscribe(self._name)
        await self._client._connection.send(message)
        self._subscribed = False
        logger.info(f"Unsubscribed from channel: {self._name}")


class PublicChannel(Channel):
    """
    Public channel - no authentication required.
    Channel names do not have a prefix.
    """

    async def _subscribe(self) -> None:
        """Subscribe without authentication."""
        message = Messages.subscribe(self._name)
        await self._client._connection.send(message)
        self._subscribed = True
        logger.info(f"Subscribed to public channel: {self._name}")


class PrivateChannel(Channel):
    """
    Private channel - requires HMAC authentication.
    Channel names are prefixed with 'private-'.
    """

    def __init__(self, name: str, client: ReverbClient) -> None:
        super().__init__(name, client)
        self._authenticator: Authenticator | None = None

    async def _subscribe(self) -> None:
        """Subscribe with HMAC signature authentication."""
        socket_id = self._client._connection.socket_id
        if not socket_id:
            raise RuntimeError("Cannot subscribe: not connected")

        # Get authenticator from client
        auth_data = self._client._authenticator.authenticate(socket_id, self._name)

        message = Messages.subscribe(self._name, auth=auth_data["auth"])
        await self._client._connection.send(message)
        self._subscribed = True
        logger.info(f"Subscribed to private channel: {self._name}")


class PresenceChannel(PrivateChannel):
    """
    Presence channel - authenticated with member tracking.
    Channel names are prefixed with 'presence-'.

    Additional features:
    - Track channel members
    - Receive member join/leave events
    - Access member list
    """

    def __init__(self, name: str, client: ReverbClient, user_data: dict[str, Any]) -> None:
        super().__init__(name, client)
        self._user_data = user_data
        self._members: dict[str, dict[str, Any]] = {}

    @property
    def members(self) -> dict[str, dict[str, Any]]:
        """Current channel members keyed by user_id."""
        return self._members.copy()

    @property
    def me(self) -> dict[str, Any]:
        """Current user's presence data."""
        return self._user_data

    async def _subscribe(self) -> None:
        """Subscribe with user data for presence."""
        socket_id = self._client._connection.socket_id
        if not socket_id:
            raise RuntimeError("Cannot subscribe: not connected")

        # Authenticate with user data
        auth_data = self._client._authenticator.authenticate(
            socket_id, self._name, user_data=self._user_data
        )

        message = Messages.subscribe(
            self._name,
            auth=auth_data["auth"],
            channel_data=auth_data.get("channel_data"),
        )
        await self._client._connection.send(message)
        self._subscribed = True
        logger.info(f"Subscribed to presence channel: {self._name}")

    async def _handle_event(self, event: str, data: Any) -> None:
        """Handle presence-specific events and dispatch to handlers."""
        # Handle member tracking
        if event == Events.SUBSCRIPTION_SUCCEEDED:
            # Initialize member list from subscription response
            if isinstance(data, dict) and "presence" in data:
                presence = data["presence"]
                members = presence.get("hash", {})
                self._members = members
                logger.debug(f"Presence channel initialized with {len(members)} members")

        elif event == Events.MEMBER_ADDED:
            user_id = data.get("user_id")
            user_info = data.get("user_info", {})
            if user_id:
                self._members[user_id] = user_info
                logger.debug(f"Member added: {user_id}")

        elif event == Events.MEMBER_REMOVED:
            user_id = data.get("user_id")
            if user_id and user_id in self._members:
                del self._members[user_id]
                logger.debug(f"Member removed: {user_id}")

        # Call parent handler
        await super()._handle_event(event, data)


def create_channel(name: str, client: ReverbClient, user_data: dict[str, Any] | None = None) -> Channel:
    """
    Factory function to create the appropriate channel type based on name prefix.

    Args:
        name: Channel name
        client: ReverbClient instance
        user_data: User data for presence channels

    Returns:
        Appropriate Channel subclass instance
    """
    if name.startswith("presence-"):
        if user_data is None:
            raise ValueError("Presence channels require user_data")
        return PresenceChannel(name, client, user_data)
    elif name.startswith("private-"):
        return PrivateChannel(name, client)
    else:
        return PublicChannel(name, client)
