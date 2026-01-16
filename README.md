# Python Reverb

Async Python client for Laravel Reverb WebSocket servers.

## Features

- Async-first design using `asyncio`
- Support for public, private, and presence channels
- HMAC-SHA256 authentication for private/presence channels
- Automatic reconnection with exponential backoff
- Client events (bidirectional communication)
- Environment variable and `.env` file configuration
- Type hints throughout

## Installation

```bash
pip install python-reverb
```

Or install from source:

```bash
pip install -e .
```

## Quick Start

```python
import asyncio
from reverb import ReverbClient

async def handle_message(event, data, channel):
    print(f"Received {event}: {data}")

async def main():
    async with ReverbClient() as client:
        channel = await client.subscribe("my-channel")
        channel.bind("my-event", handle_message)
        await client.listen()

asyncio.run(main())
```

## Configuration

Configuration can be provided via environment variables, a `.env` file, or programmatically.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REVERB_APP_KEY` | Application key | *required* |
| `REVERB_APP_SECRET` | Application secret | *required* |
| `REVERB_HOST` | Server hostname | *required* |
| `REVERB_PORT` | WebSocket port | `443` |
| `REVERB_SCHEME` | `ws` or `wss` | `wss` |
| `REVERB_RECONNECT_ENABLED` | Auto-reconnect | `true` |
| `REVERB_LOG_LEVEL` | Logging level | `INFO` |

### .env File

```env
REVERB_APP_KEY=your-app-key
REVERB_APP_SECRET=your-app-secret
REVERB_HOST=your-server.com
REVERB_PORT=443
REVERB_SCHEME=wss
```

### Programmatic Configuration

```python
from reverb import ReverbClient, ReverbConfig

config = ReverbConfig(
    app_key="your-key",
    app_secret="your-secret",
    host="localhost",
    port=8080,
    scheme="ws",
)

client = ReverbClient(config=config)
```

## Channel Types

### Public Channels

No authentication required:

```python
channel = await client.subscribe("news")
channel.bind("article-published", handler)
```

### Private Channels

Requires HMAC authentication (handled automatically):

```python
channel = await client.subscribe("private-user.123")
channel.bind("notification", handler)
```

### Presence Channels

Includes member tracking:

```python
channel = await client.subscribe(
    "presence-chat.room1",
    user_data={"user_id": "123", "user_info": {"name": "Alice"}}
)

# Access members
print(channel.members)
print(channel.me)

# Listen for member events
channel.bind("pusher_internal:member_added", on_member_join)
channel.bind("pusher_internal:member_removed", on_member_leave)
```

## Client Events

Send events from client to server:

```python
channel = await client.subscribe("private-chat.room1")

# Trigger a client event (must start with 'client-')
await channel.trigger("typing", {"user": "alice"})
```

## Running as a Service (Raspberry Pi)

See `examples/raspberry_pi_service.py` for a complete long-running service example.

### Systemd Service

Create `/etc/systemd/system/reverb-listener.service`:

```ini
[Unit]
Description=Reverb WebSocket Listener Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/reverb-service
EnvironmentFile=/home/pi/reverb-service/.env
ExecStart=/home/pi/reverb-service/venv/bin/python raspberry_pi_service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable reverb-listener
sudo systemctl start reverb-listener
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/ tests/

# Run type checker
mypy src/
```

## License

GPL-3.0-or-later
# python-reverb
