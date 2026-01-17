"""Main ReverbClient class for connecting to Laravel Reverb servers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .auth import Authenticator
from .channels import Channel, create_channel
from .config import ReverbConfig
from .connection import Connection
from .messages import Events, Message
from .types import EventHandler

logger = logging.getLogger(__name__)


class ReverbClient:
    """
    Main client for connecting to Laravel Reverb WebSocket servers.

    Example:
        async with ReverbClient(app_key="my-key", host="localhost") as client:
            channel = await client.subscribe("my-channel")
            channel.bind("my-event", handler)
            await client.listen()
    """

    def __init__(
        self,
        app_key: str | None = None,
        app_secret: str | None = None,
        host: str | None = None,
        port: int | None = None,
        *,
        config: ReverbConfig | None = None,
        scheme: str | None = None,
    ) -> None:
        """
        Initialize the Reverb client.

        Args:
            app_key: Reverb application key (or use REVERB_APP_KEY env var)
            app_secret: Reverb application secret (or use REVERB_APP_SECRET env var)
            host: Server hostname (or use REVERB_HOST env var)
            port: WebSocket port (default: 443)
            config: Optional ReverbConfig instance (overrides individual params)
            scheme: WebSocket scheme ('ws' or 'wss', default: 'wss')
        """
        # Build config from params or use provided config
        if config is not None:
            self._config = config
        else:
            # Build kwargs for config, only including non-None values
            config_kwargs: dict[str, Any] = {}
            if app_key is not None:
                config_kwargs["app_key"] = app_key
            if app_secret is not None:
                config_kwargs["app_secret"] = app_secret
            if host is not None:
                config_kwargs["host"] = host
            if port is not None:
                config_kwargs["port"] = port
            if scheme is not None:
                config_kwargs["scheme"] = scheme

            self._config = ReverbConfig(**config_kwargs)

        # Set up logging
        logging.basicConfig(level=getattr(logging, self._config.log_level.upper()))

        # Initialize authenticator
        self._authenticator = Authenticator(
            self._config.app_key,
            self._config.app_secret.get_secret_value(),
        )

        # Initialize connection
        self._connection = Connection(
            config=self._config,
            on_message=self._handle_message,
            on_connect=self._handle_connect,
            on_disconnect=self._handle_disconnect,
            on_error=self._handle_error,
        )

        # Channel management
        self._channels: dict[str, Channel] = {}
        self._pending_subscriptions: dict[str, asyncio.Event] = {}

        # Global event handlers
        self._global_handlers: dict[str, list[EventHandler]] = {}

        # State
        self._connected = False
        self._listen_task: asyncio.Task[None] | None = None

    @property
    def socket_id(self) -> str | None:
        """The socket ID assigned by the server."""
        return self._connection.socket_id

    @property
    def is_connected(self) -> bool:
        """Whether currently connected to the server."""
        return self._connection.is_connected

    @property
    def channels(self) -> dict[str, Channel]:
        """Dict of subscribed channels by name."""
        return self._channels.copy()

    async def connect(self) -> None:
        """Establish WebSocket connection to the Reverb server."""
        logger.info("Connecting to Reverb server...")
        await self._connection.connect()

    async def disconnect(self) -> None:
        """Gracefully close the connection."""
        logger.info("Disconnecting from Reverb server...")

        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        await self._connection.disconnect()
        self._channels.clear()
        self._connected = False

    async def subscribe(
        self,
        channel_name: str,
        user_data: dict[str, Any] | None = None,
    ) -> Channel:
        """
        Subscribe to a channel. Automatically detects channel type from name.

        Args:
            channel_name: Name of the channel to subscribe to
            user_data: User data for presence channels (required for presence-*)

        Returns:
            The subscribed Channel instance

        Channel types:
            - "channel-name" -> PublicChannel
            - "private-channel-name" -> PrivateChannel
            - "presence-channel-name" -> PresenceChannel
        """
        if channel_name in self._channels:
            logger.warning(f"Already subscribed to channel: {channel_name}")
            return self._channels[channel_name]

        # Create appropriate channel type
        channel = create_channel(channel_name, self, user_data)

        # Set up subscription wait event
        self._pending_subscriptions[channel_name] = asyncio.Event()

        # Send subscription request
        await channel._subscribe()

        # Store channel
        self._channels[channel_name] = channel

        logger.info(f"Subscribed to channel: {channel_name}")
        return channel

    async def unsubscribe(self, channel_name: str) -> None:
        """
        Unsubscribe from a channel.

        Args:
            channel_name: Name of the channel to unsubscribe from
        """
        if channel_name not in self._channels:
            logger.warning(f"Not subscribed to channel: {channel_name}")
            return

        channel = self._channels[channel_name]
        await channel._unsubscribe()
        del self._channels[channel_name]

    def bind(self, event: str, handler: EventHandler) -> None:
        """
        Bind a global event handler (receives events from all channels).

        Args:
            event: Event name to listen for (or '*' for all events)
            handler: Async function(event, data, channel) to call
        """
        if event not in self._global_handlers:
            self._global_handlers[event] = []
        self._global_handlers[event].append(handler)
        logger.debug(f"Bound global handler for '{event}'")

    def unbind(self, event: str, handler: EventHandler | None = None) -> None:
        """
        Remove global event handler(s).

        Args:
            event: Event name
            handler: Specific handler to remove, or None to remove all
        """
        if event in self._global_handlers:
            if handler is None:
                del self._global_handlers[event]
            else:
                self._global_handlers[event] = [
                    h for h in self._global_handlers[event] if h != handler
                ]

    async def listen(self) -> None:
        """
        Start listening for messages. Blocks until disconnected.

        This is the main loop for long-running services.
        """
        logger.info("Starting message listener...")
        try:
            while self._connection.is_connected:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Listener cancelled")
            raise

    async def _handle_message(self, message: Message) -> None:
        """Handle incoming message from connection."""
        event = message.event
        data = message.data
        channel_name = message.channel

        logger.debug(f"Handling message: {event} on {channel_name}")

        # Handle subscription confirmation
        if event == Events.SUBSCRIPTION_SUCCEEDED:
            if channel_name and channel_name in self._pending_subscriptions:
                self._pending_subscriptions[channel_name].set()
                del self._pending_subscriptions[channel_name]

        # Route to channel handlers
        if channel_name and channel_name in self._channels:
            channel = self._channels[channel_name]
            await channel._handle_event(event, data)

        # Route to global handlers
        await self._dispatch_global(event, data, channel_name)

    async def _dispatch_global(
        self, event: str, data: Any, channel_name: str | None
    ) -> None:
        """Dispatch event to global handlers."""
        handlers = self._global_handlers.get(event, []) + self._global_handlers.get("*", [])

        for handler in handlers:
            try:
                await handler(event, data, channel_name)
            except Exception as e:
                logger.error(f"Global handler error for '{event}': {e}")

    async def _handle_connect(self, socket_id: str) -> None:
        """Handle connection established."""
        self._connected = True
        logger.info(f"Connected with socket_id: {socket_id}")

        # Re-subscribe to channels after reconnection
        for channel in self._channels.values():
            if not channel.is_subscribed:
                logger.info(f"Re-subscribing to channel: {channel.name}")
                await channel._subscribe()

    async def _handle_disconnect(self) -> None:
        """Handle disconnection."""
        self._connected = False
        # Mark all channels as unsubscribed
        for channel in self._channels.values():
            channel._subscribed = False
        logger.warning("Disconnected from server")

    async def _handle_error(self, error: Exception) -> None:
        """Handle connection error."""
        logger.error(f"Connection error: {error}")

    async def __aenter__(self) -> "ReverbClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()
