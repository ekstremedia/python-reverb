#!/usr/bin/env python3
"""
Generic device listener for python-reverb.

Connects to a Laravel Reverb server and responds to commands:
- health.ping: Check if device is online
- vitals.request: Get system metrics (CPU, memory, temp, uptime)
- capture.request: Capture and upload a photo

Configure via .env file:

    REVERB_APP_KEY=your-key
    REVERB_APP_SECRET=your-secret
    REVERB_HOST=your-server.com
    DEVICE_ID=my-device-name
    API_BASE_URL=https://your-server.com
    CAPTURE_SCRIPT=/opt/scripts/capture.sh  # optional

Usage:
    python device_listener.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import signal
import sys
import time
from pathlib import Path
from typing import Any

try:
    import aiohttp
except ImportError:
    print("Error: aiohttp is required. Install with: pip install aiohttp")
    sys.exit(1)

from dotenv import load_dotenv

from reverb import ReverbClient

# Load .env file
load_dotenv()

# Configuration from environment
DEVICE_ID = os.environ.get("DEVICE_ID")
API_BASE_URL = os.environ.get("API_BASE_URL", "").rstrip("/")
API_TOKEN = os.environ.get("API_TOKEN", "")
CAPTURE_SCRIPT = os.environ.get("CAPTURE_SCRIPT", "/opt/scripts/capture.sh")
IMAGE_BASE_PATH = os.environ.get("IMAGE_BASE_PATH", "/var/www/html/images")

if not DEVICE_ID:
    print("Error: DEVICE_ID not set in .env file")
    sys.exit(1)

if not API_BASE_URL:
    print("Error: API_BASE_URL not set in .env file")
    sys.exit(1)

# Configure logging
log_level = os.environ.get("REVERB_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(f"device.{DEVICE_ID}")


class DeviceListener:
    """Listens for commands from the server and responds."""

    # Minimum seconds between capture requests
    CAPTURE_COOLDOWN = 15

    def __init__(self) -> None:
        self.client: ReverbClient | None = None
        self.running = False
        self._shutdown = asyncio.Event()
        self._http_session: aiohttp.ClientSession | None = None
        self._last_capture_time: float = 0
        self._capture_in_progress = False

    async def start(self) -> None:
        """Start the listener."""
        logger.info("starting device_id=%s", DEVICE_ID)
        logger.info("api_base_url=%s", API_BASE_URL)
        logger.info("capture_script=%s", CAPTURE_SCRIPT)
        self.running = True

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_handler)

        self._http_session = aiohttp.ClientSession()

        try:
            while self.running:
                try:
                    await self._run()
                except Exception:
                    logger.exception("connection error")
                    if self.running:
                        logger.info("reconnecting in 5s")
                        await asyncio.sleep(5)
        finally:
            if self._http_session:
                await self._http_session.close()

    async def _run(self) -> None:
        """Main connection loop."""
        async with ReverbClient() as client:
            self.client = client
            logger.info("connected socket_id=%s", client.socket_id)

            # Subscribe to device channel
            channel_name = f"device.{DEVICE_ID}"
            logger.info("subscribing to channel: %s", channel_name)
            channel = await client.subscribe(channel_name)
            logger.info("subscribed successfully, binding handlers...")

            # Bind event handlers
            channel.bind("health.ping", self._on_health_ping)
            channel.bind("vitals.request", self._on_vitals_request)
            channel.bind("capture.request", self._on_capture_request)

            # Debug: log ALL events on this channel
            channel.bind("*", self._on_any_event)

            # Also bind a global handler on the client to see ALL events
            client.bind("*", self._on_global_event)

            logger.info("listening on channel device.%s", DEVICE_ID)

            # Wait for shutdown or disconnect
            listen = asyncio.create_task(client.listen())
            shutdown = asyncio.create_task(self._shutdown.wait())

            done, pending = await asyncio.wait(
                [listen, shutdown],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

    # -------------------------------------------------------------------------
    # Debug: Log all events
    # -------------------------------------------------------------------------

    async def _on_any_event(self, event: str, data: Any, channel: str | None) -> None:
        """Debug handler - logs all received events on channel."""
        logger.debug("CHANNEL EVENT: event=%s channel=%s data=%s", event, channel, data)

    async def _on_global_event(self, event: str, data: Any, channel: str | None) -> None:
        """Debug handler - logs all global events."""
        logger.info("GLOBAL EVENT: event=%s channel=%s", event, channel)

    # -------------------------------------------------------------------------
    # 1. Health Check - Simple online/offline check
    # -------------------------------------------------------------------------

    async def _on_health_ping(self, event: str, data: Any, channel: str | None) -> None:
        """Handle health ping - responds immediately to confirm device is online."""
        request_id = data.get("request_id", "unknown")
        logger.info("health.ping received request_id=%s", request_id)

        await self._api_post("/api/device/pong", {
            "device_id": DEVICE_ID,
            "request_id": request_id,
            "status": "online",
        })

    # -------------------------------------------------------------------------
    # 2. Vitals - Detailed system metrics
    # -------------------------------------------------------------------------

    async def _on_vitals_request(self, event: str, data: Any, channel: str | None) -> None:
        """Handle vitals request - returns detailed system metrics."""
        request_id = data.get("request_id", "unknown")
        logger.info("vitals.request received request_id=%s", request_id)

        vitals = self._collect_vitals()

        await self._api_post("/api/device/vitals", {
            "device_id": DEVICE_ID,
            "request_id": request_id,
            "vitals": vitals,
        })

    def _collect_vitals(self) -> dict[str, Any]:
        """Collect detailed system vitals."""
        vitals: dict[str, Any] = {
            "platform": platform.system(),
            "hostname": platform.node(),
            "python_version": platform.python_version(),
            "machine": platform.machine(),
        }

        # Load average (Linux/macOS)
        try:
            load = os.getloadavg()
            vitals["load_1m"] = round(load[0], 2)
            vitals["load_5m"] = round(load[1], 2)
            vitals["load_15m"] = round(load[2], 2)
        except (OSError, AttributeError):
            pass

        # Memory info (Linux)
        try:
            with open("/proc/meminfo") as f:
                meminfo = {}
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        meminfo[key] = int(parts[1])

                if "MemTotal" in meminfo and "MemAvailable" in meminfo:
                    total = meminfo["MemTotal"]
                    available = meminfo["MemAvailable"]
                    vitals["mem_total_mb"] = round(total / 1024)
                    vitals["mem_available_mb"] = round(available / 1024)
                    vitals["mem_used_percent"] = round((1 - available / total) * 100, 1)
        except (OSError, FileNotFoundError, ValueError):
            pass

        # CPU temperature (Raspberry Pi)
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                temp = int(f.read().strip()) / 1000
                vitals["cpu_temp_c"] = round(temp, 1)
        except (OSError, FileNotFoundError, ValueError):
            pass

        # Uptime (Linux)
        try:
            with open("/proc/uptime") as f:
                uptime_seconds = float(f.read().split()[0])
                vitals["uptime_seconds"] = round(uptime_seconds)
                vitals["uptime_hours"] = round(uptime_seconds / 3600, 1)
                vitals["uptime_days"] = round(uptime_seconds / 86400, 2)
        except (OSError, FileNotFoundError, ValueError):
            pass

        # Disk usage
        try:
            stat = os.statvfs("/")
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            vitals["disk_total_gb"] = round(total / (1024**3), 1)
            vitals["disk_free_gb"] = round(free / (1024**3), 1)
            vitals["disk_used_percent"] = round((used / total) * 100, 1)
        except (OSError, ValueError):
            pass

        return vitals

    # -------------------------------------------------------------------------
    # 3. Capture - Execute capture script and upload photo
    # -------------------------------------------------------------------------

    async def _on_capture_request(self, event: str, data: Any, channel: str | None) -> None:
        """Handle capture request - runs capture script and uploads result."""
        request_id = data.get("request_id", "unknown")
        params = data.get("params", {})
        logger.info("capture.request received request_id=%s params=%s", request_id, params)

        # Rate limit: ignore if capture already in progress
        if self._capture_in_progress:
            logger.warning("capture.request ignored - capture already in progress request_id=%s", request_id)
            return

        # Rate limit: ignore if last capture was too recent
        now = time.time()
        since_last = now - self._last_capture_time
        if since_last < self.CAPTURE_COOLDOWN:
            logger.warning(
                "capture.request ignored - cooldown (%.1fs since last) request_id=%s",
                since_last, request_id
            )
            return

        script_path = Path(CAPTURE_SCRIPT)

        if not script_path.exists():
            logger.error("capture script not found: %s", script_path)
            await self._api_post("/api/device/capture/complete", {
                "device_id": DEVICE_ID,
                "request_id": request_id,
                "success": False,
                "error": f"Capture script not found: {script_path}",
            })
            return

        # Run capture script with rate limiting
        self._capture_in_progress = True
        self._last_capture_time = time.time()
        try:
            result = await self._run_capture_script(script_path, request_id, params)
            await self._api_post("/api/device/capture/complete", {
                "device_id": DEVICE_ID,
                "request_id": request_id,
                "success": result["success"],
                "error": result.get("error"),
                "output": result.get("output"),
                "image_path": result.get("image_path"),
            })
        except Exception as e:
            logger.exception("capture failed")
            await self._api_post("/api/device/capture/complete", {
                "device_id": DEVICE_ID,
                "request_id": request_id,
                "success": False,
                "error": str(e),
            })
        finally:
            self._capture_in_progress = False

    async def _run_capture_script(
        self, script: Path, request_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute the capture script."""
        logger.info("running capture script: %s", script)

        # Build environment with params
        env = os.environ.copy()
        env["REQUEST_ID"] = request_id
        env["DEVICE_ID"] = DEVICE_ID or ""
        env["API_BASE_URL"] = API_BASE_URL or ""
        env["API_TOKEN"] = API_TOKEN or ""
        env["IMAGE_BASE_PATH"] = IMAGE_BASE_PATH or ""

        # Pass any extra params as environment variables
        if isinstance(params, dict):
            for key, value in params.items():
                env[f"CAPTURE_{key.upper()}"] = str(value)

        proc = await asyncio.create_subprocess_exec(
            str(script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await proc.communicate()

        stdout_text = stdout.decode().strip()
        stderr_text = stderr.decode().strip()

        if proc.returncode == 0:
            logger.info("capture script succeeded: %s", stdout_text)
            return {
                "success": True,
                "output": stdout_text,
                "image_path": stdout_text if stdout_text else None,
            }
        else:
            logger.error("capture script failed (code %d): %s", proc.returncode, stderr_text)
            return {
                "success": False,
                "error": stderr_text or f"Exit code {proc.returncode}",
                "output": stdout_text,
            }

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    async def _api_post(self, endpoint: str, payload: dict[str, Any]) -> bool:
        """Send POST request to the API."""
        if not self._http_session:
            return False

        url = f"{API_BASE_URL}{endpoint}"

        try:
            async with self._http_session.post(url, json=payload) as resp:
                if resp.status == 200:
                    logger.info("POST %s success payload=%s", endpoint, payload)
                    return True
                else:
                    text = await resp.text()
                    logger.error("POST %s failed status=%d body=%s", endpoint, resp.status, text)
                    return False
        except Exception as e:
            logger.error("POST %s error: %s", endpoint, e)
            return False

    def _signal_handler(self) -> None:
        """Handle shutdown signals."""
        logger.info("shutdown signal received")
        self.running = False
        self._shutdown.set()


async def main() -> None:
    listener = DeviceListener()
    await listener.start()


if __name__ == "__main__":
    asyncio.run(main())
