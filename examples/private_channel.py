#!/usr/bin/env python3
"""
Private channel example.

Demonstrates HMAC-authenticated channel subscription.

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


async def handle_notification(event: str, data: Any, channel: str | None) -> None:
    logger.info("notification: %s", data)


async def main() -> None:
    user_id = "123"

    async with ReverbClient() as client:
        logger.info("connected socket_id=%s", client.socket_id)

        # Private channels require HMAC authentication.
        # The library handles this automatically using REVERB_APP_SECRET.
        channel = await client.subscribe(f"private-user.{user_id}")
        channel.bind("notification", handle_notification)
        channel.bind("message", handle_notification)

        logger.info("subscribed to %s", channel.name)
        await client.listen()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("shutdown")
