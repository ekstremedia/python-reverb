# python-reverb

Async Python client for Laravel Reverb WebSocket servers. Implements the Pusher protocol for real-time bidirectional communication.

## Requirements

- Python 3.9+
- Laravel Reverb server or any Pusher-compatible WebSocket server

## Installation

```bash
pip install python-reverb
```

From source:

```bash
git clone https://github.com/terje/python-reverb.git
cd python-reverb
pip install -r requirements.txt
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

## Device Listener

A ready-to-use device listener script is included for IoT/Raspberry Pi deployments:

```bash
# 1. Clone and install
git clone https://github.com/terje/python-reverb.git
cd python-reverb
python3 -m venv venv
source venv/bin/activate
pip install . aiohttp

# 2. Configure
cp .env.example .env
# Edit .env with your DEVICE_ID and server credentials

# 3. Run
python device_listener.py
```

The script:
- Reads `DEVICE_ID` from `.env` to identify itself
- Subscribes to `device.{DEVICE_ID}` channel
- Responds to commands:
  - `health.ping` - Simple online/offline check
  - `vitals.request` - Returns system metrics (CPU, memory, temperature, uptime, disk)
  - `capture.request` - Runs capture script and uploads photo (configurable via `CAPTURE_SCRIPT`)
- Auto-reconnects on connection errors

See [docs/RASPBERRY_PI_SETUP.md](docs/RASPBERRY_PI_SETUP.md) for systemd service setup.

### Quick systemd Setup

Create `/etc/systemd/system/reverb-client.service`:

```ini
[Unit]
Description=Reverb WebSocket Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/python-reverb
EnvironmentFile=/home/pi/python-reverb/.env
ExecStart=/home/pi/python-reverb/venv/bin/python device_listener.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable reverb-client
sudo systemctl start reverb-client
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
