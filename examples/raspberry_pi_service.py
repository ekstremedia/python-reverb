#!/usr/bin/env python3
"""
Long-running service for Raspberry Pi.

Listens for commands from a Reverb server and executes local actions.
Designed to run as a systemd service.

Required environment variables:
    REVERB_APP_KEY
    REVERB_APP_SECRET
    REVERB_HOST

Optional:
    DEVICE_ID - unique identifier for this device (default: hostname)
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import subprocess
from pathlib import Path
from typing import Any

from reverb import Events, ReverbClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("reverb-service")

DEVICE_ID = os.environ.get("DEVICE_ID", socket.gethostname())
SCRIPTS_DIR = Path(os.environ.get("SCRIPTS_DIR", "/opt/scripts"))


class Service:
    def __init__(self) -> None:
        self.client: ReverbClient | None = None
        self.running = False
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        logger.info("starting device_id=%s", DEVICE_ID)
        self.running = True

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_handler)

        while self.running:
            try:
                await self._run()
            except Exception:
                logger.exception("service error")
                if self.running:
                    logger.info("restarting in 5s")
                    await asyncio.sleep(5)

    async def _run(self) -> None:
        async with ReverbClient() as client:
            self.client = client

            # Device-specific private channel
            device = await client.subscribe(f"private-device.{DEVICE_ID}")
            device.bind("command", self._on_command)
            device.bind("ping", self._on_ping)

            # Global broadcast channel
            broadcast = await client.subscribe("system")
            broadcast.bind("announcement", self._on_announcement)

            client.bind(Events.ERROR, self._on_error)

            logger.info("connected socket_id=%s", client.socket_id)

            listen = asyncio.create_task(client.listen())
            shutdown = asyncio.create_task(self._shutdown.wait())

            done, pending = await asyncio.wait(
                [listen, shutdown],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

    async def _on_command(self, event: str, data: Any, channel: str | None) -> None:
        action = data.get("action")
        params = data.get("params", {})
        logger.info("command action=%s params=%s", action, params)

        if action == "run_script":
            await self._run_script(params.get("name"))
        elif action == "capture":
            await self._capture(params)
        elif action == "status":
            await self._send_status()
        elif action == "reboot":
            await self._reboot()
        else:
            logger.warning("unknown action=%s", action)

    async def _on_ping(self, event: str, data: Any, channel: str | None) -> None:
        """Respond to ping requests, typically triggered by web page visits."""
        request_id = data.get("request_id")
        logger.info("ping request_id=%s", request_id)

        # Execute configured response action
        script = SCRIPTS_DIR / "on_ping.sh"
        if script.exists():
            await self._execute(script, request_id or "")
        else:
            # Default: send acknowledgment via client event
            if self.client:
                ch = self.client.channels.get(f"private-device.{DEVICE_ID}")
                if ch:
                    await ch.trigger("pong", {
                        "device_id": DEVICE_ID,
                        "request_id": request_id,
                    })

    async def _on_announcement(self, event: str, data: Any, channel: str | None) -> None:
        logger.info("announcement: %s", data.get("message"))

    async def _on_error(self, event: str, data: Any, channel: str | None) -> None:
        logger.error("reverb error: %s", data)

    async def _run_script(self, name: str | None) -> None:
        if not name:
            return

        script = SCRIPTS_DIR / name
        if not script.exists():
            logger.error("script not found: %s", script)
            return

        await self._execute(script)

    async def _execute(self, script: Path, *args: str) -> tuple[int, str, str]:
        logger.info("executing %s %s", script, args)
        proc = await asyncio.create_subprocess_exec(
            str(script),
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            logger.info("script succeeded: %s", stdout.decode().strip())
        else:
            logger.error("script failed: %s", stderr.decode().strip())

        return proc.returncode or 0, stdout.decode(), stderr.decode()

    async def _capture(self, params: dict) -> None:
        """Capture images. Implementation depends on camera setup."""
        logger.info("capture params=%s", params)
        script = SCRIPTS_DIR / "capture.sh"
        if script.exists():
            await self._execute(script)

    async def _send_status(self) -> None:
        """Send device status back to server."""
        if not self.client:
            return

        # Collect system info
        try:
            with open("/proc/loadavg") as f:
                load = f.read().split()[0]
        except Exception:
            load = "unknown"

        ch = self.client.channels.get(f"private-device.{DEVICE_ID}")
        if ch:
            await ch.trigger("status", {
                "device_id": DEVICE_ID,
                "load": load,
            })

    async def _reboot(self) -> None:
        logger.warning("reboot requested")
        await asyncio.sleep(2)
        subprocess.run(["sudo", "reboot"], check=False)

    def _signal_handler(self) -> None:
        logger.info("shutdown signal received")
        self.running = False
        self._shutdown.set()


async def main() -> None:
    service = Service()
    await service.start()


if __name__ == "__main__":
    asyncio.run(main())
