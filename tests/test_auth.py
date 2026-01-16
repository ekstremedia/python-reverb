"""Tests for HMAC authentication."""

import hashlib
import hmac

from reverb.auth import Authenticator


class TestAuthenticator:
    """Tests for the Authenticator class."""

    def test_private_channel_signature(self, config, socket_id):
        """Test HMAC signature generation for private channels."""
        auth = Authenticator(config.app_key, config.app_secret.get_secret_value())
        channel_name = "private-user.123"

        result = auth.authenticate(socket_id, channel_name)

        assert "auth" in result
        assert result["auth"].startswith(f"{config.app_key}:")

        # Verify signature manually
        string_to_sign = f"{socket_id}:{channel_name}"
        expected_sig = hmac.new(
            config.app_secret.get_secret_value().encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert result["auth"] == f"{config.app_key}:{expected_sig}"

    def test_presence_channel_signature(self, config, socket_id):
        """Test HMAC signature generation for presence channels."""
        auth = Authenticator(config.app_key, config.app_secret.get_secret_value())
        channel_name = "presence-chat.room1"
        user_data = {"user_id": "456", "user_info": {"name": "Alice"}}

        result = auth.authenticate(socket_id, channel_name, user_data=user_data)

        assert "auth" in result
        assert "channel_data" in result
        assert result["auth"].startswith(f"{config.app_key}:")

    def test_no_channel_data_for_private(self, config, socket_id):
        """Verify private channels don't include channel_data."""
        auth = Authenticator(config.app_key, config.app_secret.get_secret_value())

        result = auth.authenticate(socket_id, "private-test")

        assert "auth" in result
        assert "channel_data" not in result
