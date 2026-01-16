#!/usr/bin/env python3
"""
Basic usage example.

Connects to a Reverb server, subscribes to a public channel,
and prints received events.

Required environment variables:
    REVERB_APP_KEY
    REVERB_APP_SECRET
    REVERB_HOST
"""

import asyncio
import logging
from typing import Any

from reverb import ReverbClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def handle_event(event: str, data: Any, channel: str | None) -> None:
    """Log received events."""
    logger.info("event=%s channel=%s data=%s", event, channel, data)


async def main() -> None:
    async with ReverbClient() as client:
        logger.info("connected socket_id=%s", client.socket_id)

        channel = await client.subscribe("notifications")
        channel.bind("alert", handle_event)
        channel.bind("info", handle_event)

        logger.info("listening on channel=%s", channel.name)
        await client.listen()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("shutdown")
