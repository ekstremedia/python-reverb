# python-reverb

Async Python client for Laravel Reverb WebSocket servers. Implements the Pusher protocol for real-time bidirectional communication.

## Requirements

- Python 3.10+
- Laravel Reverb server or any Pusher-compatible WebSocket server

## Installation

```bash
pip install python-reverb
```

From source:

```bash
git clone https://github.com/terje/python-reverb.git
cd python-reverb
pip install -e .
```

## Configuration

The client reads configuration from environment variables prefixed with `REVERB_`.

### Required

| Variable | Description |
|----------|-------------|
| `REVERB_APP_KEY` | Application key from Reverb config |
| `REVERB_APP_SECRET` | Application secret for HMAC authentication |
| `REVERB_HOST` | Reverb server hostname |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `REVERB_PORT` | `443` | WebSocket port |
| `REVERB_SCHEME` | `wss` | Protocol: `ws` or `wss` |
| `REVERB_RECONNECT_ENABLED` | `true` | Auto-reconnect on disconnect |
| `REVERB_RECONNECT_DELAY_MIN` | `1.0` | Initial reconnect delay in seconds |
| `REVERB_RECONNECT_DELAY_MAX` | `30.0` | Maximum reconnect delay in seconds |
| `REVERB_PING_INTERVAL` | `30.0` | Keepalive interval in seconds |
| `REVERB_LOG_LEVEL` | `INFO` | Logging verbosity |

### Example .env

```
REVERB_APP_KEY=your-app-key
REVERB_APP_SECRET=your-app-secret
REVERB_HOST=reverb.example.com
```

## Basic Usage

```python
import asyncio
from reverb import ReverbClient

async def handle_event(event: str, data: dict, channel: str | None) -> None:
    print(f"{channel}: {event} -> {data}")

async def main():
    async with ReverbClient() as client:
        channel = await client.subscribe("updates")
        channel.bind("data.changed", handle_event)
        await client.listen()

asyncio.run(main())
```

## Channel Types

### Public Channels

No authentication. Any client can subscribe.

```python
channel = await client.subscribe("news")
channel.bind("article.published", handler)
```

### Private Channels

HMAC-SHA256 authentication handled automatically. Channel names must start with `private-`.

```python
channel = await client.subscribe("private-user.123")
channel.bind("notification", handler)
```

### Presence Channels

Authenticated channels with member tracking. Channel names must start with `presence-`.

```python
channel = await client.subscribe(
    "presence-room.456",
    user_data={"user_id": "123", "user_info": {"name": "alice"}}
)

print(channel.members)  # dict of user_id -> user_info
print(channel.me)       # current user's data
```

## Client Events

Send events from client to server. Requires private or presence channel subscription.

```python
channel = await client.subscribe("private-device.rpi-001")
await channel.trigger("status", {"cpu": 45.2, "memory": 1024})
```

The `trigger` method automatically prefixes events with `client-` per the Pusher protocol.

## Event Binding

### Channel Events

```python
channel.bind("message.new", handle_new)
channel.bind("message.deleted", handle_deleted)
channel.bind("*", log_all)  # wildcard
```

### Global Events

Receive events from all channels:

```python
client.bind("error", handle_errors)
client.bind("*", log_everything)
```

### Unbinding

```python
channel.unbind("message.new", specific_handler)
channel.unbind("message.new")  # all handlers for this event
```

## Presence Events

```python
from reverb import Events

async def on_join(event, data, channel):
    print(f"Joined: {data['user_id']}")

async def on_leave(event, data, channel):
    print(f"Left: {data['user_id']}")

channel.bind(Events.MEMBER_ADDED, on_join)
channel.bind(Events.MEMBER_REMOVED, on_leave)
```

## Use Cases

### IoT Device Control

Raspberry Pi connecting to a central server for remote commands:

```python
import os
from reverb import ReverbClient

DEVICE_ID = os.environ.get("DEVICE_ID", "rpi-001")

async def main():
    async with ReverbClient() as client:
        device = await client.subscribe(f"private-device.{DEVICE_ID}")

        async def handle_command(event, data, channel):
            action = data.get("action")
            if action == "capture":
                path = capture_image()
                upload(path, data.get("request_id"))
            elif action == "reboot":
                os.system("sudo reboot")

        device.bind("command", handle_command)
        await client.listen()
```

### Real-time Data Sync

Backend service receiving updates pushed from the web application:

```python
async def main():
    async with ReverbClient() as client:
        channel = await client.subscribe("private-sync.inventory")

        async def on_update(event, data, channel):
            item_id = data["id"]
            new_quantity = data["quantity"]
            update_local_database(item_id, new_quantity)

        channel.bind("item.updated", on_update)
        await client.listen()
```

### Chat Moderation Bot

Monitor chat rooms for content moderation:

```python
async def main():
    async with ReverbClient() as client:
        room = await client.subscribe(
            "presence-chat.general",
            user_data={"user_id": "bot-moderator", "user_info": {"name": "ModBot"}}
        )

        async def moderate(event, data, channel):
            if is_spam(data.get("text", "")):
                await flag_message(data["message_id"])

        room.bind("client-message", moderate)
        await client.listen()
```

### Webhook Relay

Forward incoming webhooks to WebSocket subscribers:

```python
from aiohttp import web
from reverb import ReverbClient

async def webhook_handler(request):
    payload = await request.json()
    source = request.match_info["source"]

    async with ReverbClient() as client:
        await client.connect()
        channel = await client.subscribe(f"private-webhooks.{source}")
        await channel.trigger("received", payload)

    return web.Response(status=200)
```

## Running as a System Service

### systemd

Create `/etc/systemd/system/reverb-client.service`:

```ini
[Unit]
Description=Reverb WebSocket Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/app
EnvironmentFile=/home/pi/app/.env
ExecStart=/home/pi/app/venv/bin/python listener.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable reverb-client
sudo systemctl start reverb-client
```

View logs:

```bash
sudo journalctl -u reverb-client -f
```

## Error Handling

```python
from reverb import ReverbClient, ConnectionError, AuthenticationError

try:
    async with ReverbClient() as client:
        channel = await client.subscribe("private-secure")
        await client.listen()
except AuthenticationError:
    print("Invalid credentials")
except ConnectionError:
    print("Failed to connect")
```

## API Reference

### ReverbClient

**Methods:**

| Method | Description |
|--------|-------------|
| `connect()` | Establish WebSocket connection |
| `disconnect()` | Close connection |
| `subscribe(channel, user_data=None)` | Subscribe to channel, returns `Channel` |
| `unsubscribe(channel)` | Unsubscribe from channel |
| `bind(event, handler)` | Global event handler |
| `unbind(event, handler=None)` | Remove global handler |
| `listen()` | Block and process messages |

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `socket_id` | `str \| None` | Connection identifier |
| `is_connected` | `bool` | Connection state |
| `channels` | `dict[str, Channel]` | Subscribed channels |

### Channel

**Methods:**

| Method | Description |
|--------|-------------|
| `bind(event, handler)` | Add handler, returns self |
| `unbind(event, handler=None)` | Remove handler, returns self |
| `trigger(event, data)` | Send client event |

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Channel name |
| `is_subscribed` | `bool` | Subscription state |

### PresenceChannel

Extends `Channel`:

| Property | Type | Description |
|----------|------|-------------|
| `members` | `dict[str, dict]` | Members by user_id |
| `me` | `dict` | Current user data |

### Events

Protocol event constants:

```python
Events.CONNECTION_ESTABLISHED  # pusher:connection_established
Events.SUBSCRIPTION_SUCCEEDED  # pusher_internal:subscription_succeeded
Events.MEMBER_ADDED            # pusher_internal:member_added
Events.MEMBER_REMOVED          # pusher_internal:member_removed
Events.ERROR                   # pusher:error
```

### Exceptions

| Exception | Description |
|-----------|-------------|
| `ReverbError` | Base exception |
| `ConnectionError` | Connection failed |
| `AuthenticationError` | Channel auth failed |
| `SubscriptionError` | Subscription failed |
| `ProtocolError` | Invalid message |
| `TimeoutError` | Operation timeout |

## Development

```bash
git clone https://github.com/terje/python-reverb.git
cd python-reverb
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

pytest                      # run tests
ruff check src/ tests/      # lint
mypy src/                   # type check
```

## License

GPL-3.0-or-later
