"""Configuration management for Python Reverb."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ReverbConfig(BaseSettings):
    """
    Configuration for Reverb client.

    Values are loaded from (in order of precedence):
    1. Constructor arguments
    2. Environment variables (prefixed with REVERB_)
    3. .env file
    4. Default values
    """

    model_config = SettingsConfigDict(
        env_prefix="REVERB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required settings
    app_key: str = Field(..., description="Reverb application key")
    app_secret: SecretStr = Field(..., description="Reverb application secret")
    host: str = Field(..., description="Reverb server hostname")

    # Optional settings with defaults
    port: int = Field(default=443, description="WebSocket port")
    scheme: Literal["ws", "wss"] = Field(default="wss", description="WebSocket scheme")

    # Protocol settings
    protocol_version: int = Field(default=7, description="Pusher protocol version")
    client_name: str = Field(default="python-reverb", description="Client identifier")
    client_version: str = Field(default="0.1.0", description="Client version")

    # Reconnection settings
    reconnect_enabled: bool = Field(default=True, description="Enable auto-reconnect")
    reconnect_delay_min: float = Field(default=1.0, description="Min reconnect delay (seconds)")
    reconnect_delay_max: float = Field(default=30.0, description="Max reconnect delay (seconds)")
    reconnect_delay_multiplier: float = Field(default=2.0, description="Backoff multiplier")
    max_reconnect_attempts: Optional[int] = Field(
        default=None, description="Max attempts (None=infinite)"
    )

    # Keepalive settings
    ping_interval: float = Field(default=30.0, description="Ping interval (seconds)")
    ping_timeout: float = Field(default=10.0, description="Ping timeout (seconds)")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    def build_url(self) -> str:
        """Construct the WebSocket connection URL."""
        base = f"{self.scheme}://{self.host}:{self.port}"
        path = f"/app/{self.app_key}"
        params = (
            f"?protocol={self.protocol_version}"
            f"&client={self.client_name}"
            f"&version={self.client_version}"
        )
        return f"{base}{path}{params}"
