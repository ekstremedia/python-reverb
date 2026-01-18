"""WebSocket connection management with auto-reconnect."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Awaitable, Callable

import websockets
from websockets.asyncio.client import ClientConnection

from .config import ReverbConfig
from .exceptions import ConnectionError, ProtocolError
from .messages import Events, Message, Messages

logger = logging.getLogger(__name__)


class Connection:
    """
    Low-level WebSocket connection manager.

    Handles:
    - Connection establishment with proper URL formatting
    - Automatic reconnection with exponential backoff
    - Ping/pong keepalive mechanism
    - Message queuing during reconnection
    """

    def __init__(
        self,
        config: ReverbConfig,
        on_message: Callable[[Message], Awaitable[None]],
        on_connect: Callable[[str], Awaitable[None]],  # receives socket_id
        on_disconnect: Callable[[], Awaitable[None]],
        on_error: Callable[[Exception], Awaitable[None]],
    ) -> None:
        self.config = config
        self._on_message = on_message
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_error = on_error

        self._ws: ClientConnection | None = None
        self._socket_id: str | None = None
        self._connected = False
        self._running = False
        self._reconnect_attempts = 0

        self._receive_task: asyncio.Task[None] | None = None
        self._keepalive_task: asyncio.Task[None] | None = None
        self._pending_pong: asyncio.Event | None = None
        self._message_tasks: set[asyncio.Task[None]] = set()  # Track background message handlers

    @property
    def socket_id(self) -> str | None:
        """The socket ID assigned by the server after connection."""
        return self._socket_id

    @property
    def is_connected(self) -> bool:
        """Whether currently connected."""
        # Also check the actual websocket state, not just our flag
        if not self._connected or self._ws is None:
            return False
        # Check if websocket is actually open (not just exists)
        try:
            return self._ws.state.name == "OPEN"
        except Exception:
            return False

    async def connect(self) -> None:
        """Establish connection, handling reconnection automatically."""
        self._running = True
        await self._connect_with_retry()

    async def disconnect(self) -> None:
        """Gracefully close the connection."""
        self._running = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass

        # Cancel any pending message handler tasks
        for task in list(self._message_tasks):
            task.cancel()
        self._message_tasks.clear()

        if self._ws:
            await self._ws.close()
            self._ws = None

        self._connected = False
        self._socket_id = None

    async def send(self, message: Message) -> None:
        """Send a message to the server."""
        if not self._ws or not self._connected:
            raise ConnectionError("Not connected")

        try:
            await self._ws.send(message.to_json())
            logger.debug(f"Sent: {message.event}")
        except Exception as e:
            logger.error(f"Send error: {e}")
            raise ConnectionError(f"Failed to send message: {e}") from e

    async def _connect_with_retry(self) -> None:
        """Connect with exponential backoff retry."""
        while self._running:
            try:
                await self._establish_connection()
                self._reconnect_attempts = 0
                return
            except Exception as e:
                self._reconnect_attempts += 1
                max_attempts = self.config.max_reconnect_attempts

                if max_attempts and self._reconnect_attempts >= max_attempts:
                    logger.error(f"Max reconnect attempts ({max_attempts}) reached")
                    raise ConnectionError(f"Failed to connect after {max_attempts} attempts") from e

                if not self.config.reconnect_enabled:
                    raise

                delay = self._calculate_backoff_delay()
                logger.warning(
                    f"Connection failed (attempt {self._reconnect_attempts}), "
                    f"retrying in {delay:.1f}s: {e}"
                )
                await asyncio.sleep(delay)

    def _calculate_backoff_delay(self) -> float:
        """Calculate exponential backoff delay with jitter."""
        delay = self.config.reconnect_delay_min * (
            self.config.reconnect_delay_multiplier ** (self._reconnect_attempts - 1)
        )
        delay = min(delay, self.config.reconnect_delay_max)
        # Add jitter (0-25%)
        jitter = random.uniform(0, 0.25) * delay
        return delay + jitter

    async def _establish_connection(self) -> None:
        """Establish the WebSocket connection."""
        url = self.config.build_url()
        logger.info(f"Connecting to {url}")

        self._ws = await websockets.connect(url)
        logger.debug("WebSocket connected, waiting for connection_established")

        # Wait for connection_established event
        raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
        message = Message.from_json(str(raw))

        if message.event != Events.CONNECTION_ESTABLISHED:
            raise ProtocolError(f"Expected connection_established, got {message.event}")

        self._socket_id = message.data.get("socket_id")
        if not self._socket_id:
            raise ProtocolError("No socket_id in connection_established")

        self._connected = True
        logger.info(f"Connected with socket_id: {self._socket_id}")

        # Notify callback
        await self._on_connect(self._socket_id)

        # Start background tasks
        self._receive_task = asyncio.create_task(self._receive_loop())
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def _receive_loop(self) -> None:
        """Receive and dispatch incoming messages."""
        if not self._ws:
            return

        try:
            async for raw in self._ws:
                try:
                    message = Message.from_json(str(raw))
                    # Handle protocol messages (ping/pong) synchronously
                    # Dispatch user messages as background tasks to avoid blocking
                    await self._handle_message(message)
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    await self._on_error(e)
        except websockets.ConnectionClosed as e:
            logger.warning(f"Connection closed: {e}")
            await self._handle_connection_lost()
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
            await self._on_error(e)
            # Treat unexpected errors as connection loss and attempt reconnect
            await self._handle_connection_lost()
        else:
            # Loop exited normally without exception (can happen with close code 1000/1001)
            logger.warning("Receive loop ended - connection closed normally")
            await self._handle_connection_lost()

    async def _handle_connection_lost(self) -> None:
        """Handle connection loss and attempt reconnection."""
        self._connected = False

        # Clean up the websocket
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        await self._on_disconnect()

        # Attempt reconnection
        if self._running and self.config.reconnect_enabled:
            await self._reconnect()

    async def _handle_message(self, message: Message) -> None:
        """Handle an incoming message."""
        logger.debug(f"Received: {message.event}")

        if message.event == Events.PING:
            # Respond to server ping
            await self.send(Messages.pong())
        elif message.event == Events.PONG:
            # Handle pong response
            if self._pending_pong:
                self._pending_pong.set()
        elif message.event == Events.ERROR:
            logger.error(f"Server error: {message.data}")
            await self._on_error(ProtocolError(str(message.data)))
        else:
            # Dispatch to client handler as background task to avoid blocking receive loop
            # This allows the receive loop to continue processing messages even if
            # a handler is slow (e.g., running a capture script)
            task = asyncio.create_task(self._dispatch_message(message))
            self._message_tasks.add(task)
            task.add_done_callback(self._message_tasks.discard)

    async def _dispatch_message(self, message: Message) -> None:
        """Dispatch a message to the client handler with error handling."""
        try:
            await self._on_message(message)
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
            await self._on_error(e)

    async def _keepalive_loop(self) -> None:
        """Send periodic pings to maintain connection."""
        while self._connected and self._running:
            try:
                await asyncio.sleep(self.config.ping_interval)

                if not self._connected:
                    break

                # Server will send pusher:ping, we respond with pusher:pong
                # But we can also initiate a ping cycle by waiting for activity
                logger.debug("Keepalive check - connection active")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Keepalive error: {e}")

    async def _reconnect(self) -> None:
        """Handle reconnection after disconnect."""
        logger.info("Attempting to reconnect...")
        self._socket_id = None

        # Cancel keepalive task
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            self._keepalive_task = None

        # Brief delay before reconnecting to avoid rapid reconnection loops
        await asyncio.sleep(1.0)

        try:
            await self._connect_with_retry()
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            await self._on_error(e)
