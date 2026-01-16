"""HMAC-SHA256 authentication for private/presence channels."""

import hashlib
import hmac
import json
from typing import Any


class Authenticator:
    """
    Handles HMAC-SHA256 authentication for private/presence channels.

    The signature is computed as:
        HMAC-SHA256(app_secret, f"{socket_id}:{channel_name}")

    For presence channels, user data is included:
        HMAC-SHA256(app_secret, f"{socket_id}:{channel_name}:{user_data_json}")
    """

    def __init__(self, app_key: str, app_secret: str) -> None:
        self.app_key = app_key
        self.app_secret = app_secret

    def authenticate(
        self,
        socket_id: str,
        channel_name: str,
        user_data: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """
        Generate authentication payload for channel subscription.

        Args:
            socket_id: The socket ID from connection established event
            channel_name: The channel to authenticate for
            user_data: User data for presence channels (must include 'user_id')

        Returns:
            Dict with 'auth' key, and 'channel_data' for presence channels
        """
        if user_data is not None:
            # Presence channel
            channel_data = json.dumps(user_data, separators=(",", ":"))
            string_to_sign = f"{socket_id}:{channel_name}:{channel_data}"
            return {
                "auth": self._sign(string_to_sign),
                "channel_data": channel_data,
            }
        else:
            # Private channel
            string_to_sign = f"{socket_id}:{channel_name}"
            return {"auth": self._sign(string_to_sign)}

    def _sign(self, message: str) -> str:
        """
        Generate HMAC-SHA256 signature.

        Returns:
            String in format "app_key:hex_digest"
        """
        signature = hmac.new(
            self.app_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{self.app_key}:{signature}"
