"""Pytest fixtures for Python Reverb tests."""

import pytest

from reverb.config import ReverbConfig


@pytest.fixture
def config() -> ReverbConfig:
    """Create a test configuration."""
    return ReverbConfig(
        app_key="test-key",
        app_secret="test-secret-32-characters-long!",
        host="localhost",
        port=8080,
        scheme="ws",
    )


@pytest.fixture
def socket_id() -> str:
    """Sample socket ID for testing."""
    return "123456.7890123"
