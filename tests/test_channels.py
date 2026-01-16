"""Tests for channel abstractions."""

import pytest

from reverb.channels import (
    Channel,
    PresenceChannel,
    PrivateChannel,
    PublicChannel,
    create_channel,
)


class TestCreateChannel:
    """Tests for the create_channel factory function."""

    def test_create_public_channel(self):
        """Test creating a public channel."""
        # We can't fully test without a client, but we can test the factory logic
        # by checking exceptions
        channel = create_channel("my-channel", client=None)  # type: ignore
        assert isinstance(channel, PublicChannel)

    def test_create_private_channel(self):
        """Test creating a private channel."""
        channel = create_channel("private-user.123", client=None)  # type: ignore
        assert isinstance(channel, PrivateChannel)

    def test_create_presence_channel(self):
        """Test creating a presence channel."""
        user_data = {"user_id": "123", "user_info": {"name": "Alice"}}
        channel = create_channel("presence-chat.room1", client=None, user_data=user_data)  # type: ignore
        assert isinstance(channel, PresenceChannel)

    def test_presence_requires_user_data(self):
        """Test that presence channels require user_data."""
        with pytest.raises(ValueError, match="require user_data"):
            create_channel("presence-chat.room1", client=None)  # type: ignore


class TestPublicChannel:
    """Tests for the PublicChannel class."""

    def test_channel_name(self):
        """Test channel name property."""
        channel = PublicChannel("test-channel", client=None)  # type: ignore
        assert channel.name == "test-channel"

    def test_initial_state(self):
        """Test initial subscription state."""
        channel = PublicChannel("test-channel", client=None)  # type: ignore
        assert channel.is_subscribed is False

    def test_bind_handler(self):
        """Test binding an event handler."""
        channel = PublicChannel("test-channel", client=None)  # type: ignore

        async def handler(event, data, channel_name):
            pass

        result = channel.bind("my-event", handler)

        assert result is channel  # Returns self for chaining
        assert "my-event" in channel._handlers
        assert handler in channel._handlers["my-event"]

    def test_unbind_handler(self):
        """Test unbinding an event handler."""
        channel = PublicChannel("test-channel", client=None)  # type: ignore

        async def handler(event, data, channel_name):
            pass

        channel.bind("my-event", handler)
        channel.unbind("my-event", handler)

        assert handler not in channel._handlers.get("my-event", [])

    def test_unbind_all_handlers(self):
        """Test unbinding all handlers for an event."""
        channel = PublicChannel("test-channel", client=None)  # type: ignore

        async def handler1(event, data, channel_name):
            pass

        async def handler2(event, data, channel_name):
            pass

        channel.bind("my-event", handler1)
        channel.bind("my-event", handler2)
        channel.unbind("my-event")

        assert "my-event" not in channel._handlers


class TestPresenceChannel:
    """Tests for the PresenceChannel class."""

    def test_user_data(self):
        """Test presence channel user data."""
        user_data = {"user_id": "123", "user_info": {"name": "Alice"}}
        channel = PresenceChannel("presence-chat", client=None, user_data=user_data)  # type: ignore

        assert channel.me == user_data

    def test_initial_members_empty(self):
        """Test that members list starts empty."""
        user_data = {"user_id": "123"}
        channel = PresenceChannel("presence-chat", client=None, user_data=user_data)  # type: ignore

        assert channel.members == {}

    def test_members_returns_copy(self):
        """Test that members property returns a copy."""
        user_data = {"user_id": "123"}
        channel = PresenceChannel("presence-chat", client=None, user_data=user_data)  # type: ignore
        channel._members = {"123": {"name": "Alice"}}

        members = channel.members
        members["456"] = {"name": "Bob"}

        # Original should not be modified
        assert "456" not in channel._members
