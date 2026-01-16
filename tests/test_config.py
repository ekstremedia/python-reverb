"""Tests for configuration management."""

import pytest

from reverb.config import ReverbConfig


class TestReverbConfig:
    """Tests for the ReverbConfig class."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(Exception):  # ValidationError
            ReverbConfig()

    def test_default_values(self, config):
        """Test default configuration values."""
        assert config.port == 8080  # Override in fixture
        assert config.scheme == "ws"
        assert config.protocol_version == 7
        assert config.reconnect_enabled is True
        assert config.ping_interval == 30.0

    def test_build_url(self, config):
        """Test WebSocket URL construction."""
        url = config.build_url()

        assert url.startswith("ws://localhost:8080/app/test-key")
        assert "protocol=7" in url
        assert "client=python-reverb" in url

    def test_build_url_wss(self):
        """Test WebSocket URL with TLS."""
        config = ReverbConfig(
            app_key="key",
            app_secret="secret",
            host="example.com",
            scheme="wss",
        )

        url = config.build_url()

        assert url.startswith("wss://example.com:443/app/key")

    def test_secret_is_secret(self, config):
        """Test that app_secret is a SecretStr."""
        # Should not expose secret in string representation
        assert "test-secret" not in str(config)
        assert "test-secret" not in repr(config)

        # But can get the actual value when needed
        assert "test-secret" in config.app_secret.get_secret_value()
