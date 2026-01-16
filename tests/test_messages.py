"""Tests for message parsing and construction."""

import json

from reverb.messages import Events, Message, Messages


class TestMessage:
    """Tests for the Message class."""

    def test_from_json_basic(self):
        """Test parsing a basic message."""
        raw = json.dumps({"event": "test.event", "data": {"key": "value"}})

        msg = Message.from_json(raw)

        assert msg.event == "test.event"
        assert msg.data == {"key": "value"}
        assert msg.channel is None

    def test_from_json_with_channel(self):
        """Test parsing a message with channel."""
        raw = json.dumps({
            "event": "my.event",
            "channel": "my-channel",
            "data": {"foo": "bar"},
        })

        msg = Message.from_json(raw)

        assert msg.event == "my.event"
        assert msg.channel == "my-channel"
        assert msg.data == {"foo": "bar"}

    def test_from_json_double_encoded_data(self):
        """Test parsing a message with double-encoded data (Pusher protocol)."""
        inner_data = json.dumps({"socket_id": "123.456"})
        raw = json.dumps({
            "event": "pusher:connection_established",
            "data": inner_data,
        })

        msg = Message.from_json(raw)

        assert msg.event == "pusher:connection_established"
        assert msg.data == {"socket_id": "123.456"}

    def test_from_json_string_data(self):
        """Test parsing a message with non-JSON string data."""
        raw = json.dumps({"event": "test", "data": "plain string"})

        msg = Message.from_json(raw)

        assert msg.data == "plain string"

    def test_to_json(self):
        """Test serializing a message."""
        msg = Message(event="test.event", data={"key": "value"}, channel="test-channel")

        result = json.loads(msg.to_json())

        assert result["event"] == "test.event"
        assert result["channel"] == "test-channel"
        # Data should be JSON-encoded string
        assert json.loads(result["data"]) == {"key": "value"}

    def test_to_json_without_channel(self):
        """Test serializing a message without channel."""
        msg = Message(event="test", data={})

        result = json.loads(msg.to_json())

        assert "channel" not in result


class TestMessages:
    """Tests for the Messages factory class."""

    def test_subscribe_public(self):
        """Test creating a subscribe message for public channel."""
        msg = Messages.subscribe("my-channel")

        assert msg.event == Events.SUBSCRIBE
        assert msg.data == {"channel": "my-channel"}

    def test_subscribe_private(self):
        """Test creating a subscribe message for private channel."""
        msg = Messages.subscribe("private-channel", auth="key:signature")

        assert msg.event == Events.SUBSCRIBE
        assert msg.data["channel"] == "private-channel"
        assert msg.data["auth"] == "key:signature"

    def test_subscribe_presence(self):
        """Test creating a subscribe message for presence channel."""
        msg = Messages.subscribe(
            "presence-channel",
            auth="key:signature",
            channel_data='{"user_id":"123"}',
        )

        assert msg.event == Events.SUBSCRIBE
        assert msg.data["channel"] == "presence-channel"
        assert msg.data["auth"] == "key:signature"
        assert msg.data["channel_data"] == '{"user_id":"123"}'

    def test_unsubscribe(self):
        """Test creating an unsubscribe message."""
        msg = Messages.unsubscribe("my-channel")

        assert msg.event == Events.UNSUBSCRIBE
        assert msg.data == {"channel": "my-channel"}

    def test_pong(self):
        """Test creating a pong message."""
        msg = Messages.pong()

        assert msg.event == Events.PONG

    def test_client_event(self):
        """Test creating a client event message."""
        msg = Messages.client_event("my-channel", "typing", {"user": "alice"})

        assert msg.event == "client-typing"
        assert msg.channel == "my-channel"
        assert msg.data == {"user": "alice"}
