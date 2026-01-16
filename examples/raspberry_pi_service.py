#!/usr/bin/env python3
"""
Long-running Reverb listener service for Raspberry Pi.

This script connects to a Reverb server and listens for events,
executing local commands or actions based on received messages.

Usage:
    python raspberry_pi_service.py

Environment:
    REVERB_APP_KEY: Your Reverb application key
    REVERB_APP_SECRET: Your Reverb application secret
    REVERB_HOST: Reverb server hostname
    REVERB_PORT: WebSocket port (default: 443)
    REVERB_SCHEME: ws or wss (default: wss)
"""

import asyncio
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from reverb import Events, ReverbClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        # Uncomment to log to file:
        # logging.FileHandler("/var/log/reverb-service.log"),
    ],
)
logger = logging.getLogger("reverb-service")


class ReverbService:
    """Long-running service that listens to Reverb events."""

    def __init__(self) -> None:
        self.client: ReverbClient | None = None
        self.running = False
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the service."""
        logger.info("Starting Reverb service...")
        self.running = True

        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown)

        while self.running:
            try:
                await self._run()
            except Exception as e:
                logger.error(f"Service error: {e}", exc_info=True)
                if self.running:
                    logger.info("Restarting in 5 seconds...")
                    await asyncio.sleep(5)

    async def _run(self) -> None:
        """Main service loop."""
        async with ReverbClient() as client:
            self.client = client

            # Subscribe to device control channel
            # You can customize this channel name based on your setup
            device_id = os.environ.get("DEVICE_ID", "raspberry-pi-001")
            device_channel = await client.subscribe(f"private-device.{device_id}")
            device_channel.bind("command", self._handle_command)
            device_channel.bind("ping", self._handle_ping)

            # Subscribe to broadcast channel for system-wide events
            broadcast = await client.subscribe("system-broadcast")
            broadcast.bind("announcement", self._handle_announcement)

            # Global error handler
            client.bind(Events.ERROR, self._handle_error)

            logger.info("Connected and subscribed. Listening for events...")

            # Listen until shutdown signal
            listen_task = asyncio.create_task(client.listen())
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())

            done, pending = await asyncio.wait(
                [listen_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

    async def _handle_command(self, event: str, data: Any, channel: str | None) -> None:
        """Handle incoming command events."""
        action = data.get("action")
        params = data.get("params", {})

        logger.info(f"Received command: {action} with params: {params}")

        # Example command handlers - customize based on your needs
        if action == "run_script":
            await self._run_script(params.get("script_name"))
        elif action == "capture_image":
            await self._capture_image(params)
        elif action == "send_status":
            await self._send_status()
        elif action == "reboot":
            await self._reboot()
        else:
            logger.warning(f"Unknown command: {action}")

    async def _handle_ping(self, event: str, data: Any, channel: str | None) -> None:
        """
        Handle ping events from the web server.

        This is the callback that triggers when users visit your webpage.
        """
        logger.info(f"Received ping: {data}")

        # Example: Capture and send images when pinged
        request_id = data.get("request_id")
        if request_id:
            await self._capture_and_send_images(request_id)

    async def _capture_and_send_images(self, request_id: str) -> None:
        """Capture images and send them to the web server."""
        logger.info(f"Capturing images for request: {request_id}")

        # Example: Run a script that captures images
        script_path = Path("/opt/scripts/capture_images.sh")
        if script_path.exists():
            try:
                process = await asyncio.create_subprocess_exec(
                    str(script_path),
                    request_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    logger.info(f"Images captured successfully: {stdout.decode()}")
                else:
                    logger.error(f"Image capture failed: {stderr.decode()}")
            except Exception as e:
                logger.error(f"Failed to capture images: {e}")
        else:
            logger.warning(f"Capture script not found: {script_path}")

            # Example fallback: Send a client event back
            if self.client:
                channel = self.client.channels.get("system-broadcast")
                if channel:
                    await channel.trigger("image-ready", {
                        "request_id": request_id,
                        "device_id": os.environ.get("DEVICE_ID", "unknown"),
                        "status": "script_not_found",
                    })

    async def _handle_announcement(self, event: str, data: Any, channel: str | None) -> None:
        """Handle system announcements."""
        logger.info(f"System announcement: {data.get('message')}")

    async def _handle_error(self, event: str, data: Any, channel: str | None) -> None:
        """Handle Reverb errors."""
        logger.error(f"Reverb error: {data}")

    async def _run_script(self, script_name: str | None) -> None:
        """Execute a local script."""
        if not script_name:
            return

        script_path = Path(f"/opt/scripts/{script_name}")
        if not script_path.exists():
            logger.error(f"Script not found: {script_path}")
            return

        try:
            process = await asyncio.create_subprocess_exec(
                str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"Script {script_name} completed successfully")
            else:
                logger.error(f"Script {script_name} failed: {stderr.decode()}")
        except Exception as e:
            logger.error(f"Failed to run script: {e}")

    async def _capture_image(self, params: dict) -> None:
        """Capture an image (example - customize for your camera setup)."""
        logger.info(f"Capturing image with params: {params}")
        # Add your image capture logic here
        # e.g., using picamera2, OpenCV, or calling a capture script

    async def _send_status(self) -> None:
        """Send device status back to the server."""
        logger.info("Sending device status...")
        # Add your status reporting logic here

    async def _reboot(self) -> None:
        """Reboot the system."""
        logger.warning("Reboot requested - rebooting in 5 seconds...")
        await asyncio.sleep(5)
        subprocess.run(["sudo", "reboot"], check=False)

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info("Shutdown signal received")
        self.running = False
        self._shutdown_event.set()


async def main() -> None:
    """Entry point."""
    service = ReverbService()
    await service.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
        sys.exit(0)
