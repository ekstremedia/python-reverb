# Architecture

This document describes the internal architecture of python-reverb for contributors and users who need to understand the implementation details.

## Overview

python-reverb implements the Pusher WebSocket protocol (version 7) used by Laravel Reverb. The library is built on asyncio and uses the `websockets` library for WebSocket communication.

```
┌─────────────────────────────────────────────────────────────┐
│                        ReverbClient                          │
│  User-facing API. Manages channels and dispatches events.   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                        Connection                            │
│  WebSocket lifecycle, reconnection, keepalive.              │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  PublicChannel  │ │ PrivateChannel  │ │ PresenceChannel │
└─────────────────┘ └─────────────────┘ └─────────────────┘
                           │
                           ▼
                   ┌─────────────────┐
                   │  Authenticator  │
                   │  HMAC-SHA256    │
                   └─────────────────┘
```

## Module Structure

### client.py

`ReverbClient` is the primary interface. Responsibilities:

- Connection lifecycle management
- Channel subscription registry
- Global event dispatch
- Re-subscription after reconnection

### connection.py

`Connection` handles the WebSocket transport layer:

- Establishes WebSocket connection with protocol parameters
- Implements exponential backoff reconnection
- Responds to server ping with pong
- Routes received messages to the client

### channels.py

Channel hierarchy:

```
Channel (ABC)
├── PublicChannel
└── PrivateChannel
    └── PresenceChannel
```

Each channel maintains its own event handlers. `PresenceChannel` additionally tracks member state.

### auth.py

`Authenticator` generates HMAC-SHA256 signatures for private and presence channels:

```
Private:  HMAC(secret, "{socket_id}:{channel}")
Presence: HMAC(secret, "{socket_id}:{channel}:{user_data_json}")
```

### messages.py

`Message` handles serialization and deserialization of Pusher protocol messages. The protocol uses double-encoded JSON for system events (data field contains a JSON string).

### config.py

`ReverbConfig` uses pydantic-settings to load configuration from environment variables and `.env` files.

## Pusher Protocol

### Connection URL

```
wss://{host}:{port}/app/{app_key}?protocol=7&client=python-reverb&version=0.1.0
```

### Message Format

All messages are JSON with this structure:

```json
{
  "event": "event-name",
  "channel": "channel-name",
  "data": "{\"key\":\"value\"}"
}
```

Note: `data` is a JSON-encoded string, not a nested object.

### Connection Flow

1. Client opens WebSocket
2. Server sends `pusher:connection_established` with `socket_id`
3. Client stores `socket_id` for authentication
4. Client subscribes to channels

### Subscription

**Public channel:**
```json
{"event": "pusher:subscribe", "data": {"channel": "my-channel"}}
```

**Private channel:**
```json
{
  "event": "pusher:subscribe",
  "data": {
    "channel": "private-my-channel",
    "auth": "app_key:hmac_signature"
  }
}
```

**Presence channel:**
```json
{
  "event": "pusher:subscribe",
  "data": {
    "channel": "presence-my-channel",
    "auth": "app_key:hmac_signature",
    "channel_data": "{\"user_id\":\"123\",\"user_info\":{\"name\":\"alice\"}}"
  }
}
```

### Server Events

| Event | Description |
|-------|-------------|
| `pusher:connection_established` | Connection ready, provides `socket_id` |
| `pusher:ping` | Server keepalive, client must respond with `pusher:pong` |
| `pusher:error` | Error notification |
| `pusher_internal:subscription_succeeded` | Subscription confirmed |
| `pusher_internal:member_added` | User joined presence channel |
| `pusher_internal:member_removed` | User left presence channel |

### Client Events

Events prefixed with `client-` are forwarded to other subscribers on the same channel. The server does not process these; it relays them directly.

```json
{
  "event": "client-typing",
  "channel": "private-chat.room1",
  "data": "{\"user\":\"alice\"}"
}
```

Client events require:
- Private or presence channel subscription
- Server configuration to allow client events

## Connection State Detection

The `is_connected` property performs multiple checks to ensure accurate connection state:

1. Checks the internal `_connected` flag
2. Verifies the websocket object exists
3. **Checks the actual websocket state** - ensures the websocket is in the "OPEN" state

This multi-layered check is important because the websockets library can close a connection internally (e.g., due to a ping timeout) without our code being immediately notified. By checking `ws.state.name == "OPEN"`, we detect when the underlying connection has closed even if the receive loop hasn't processed the close event yet.

## Reconnection Strategy

When connection drops:

1. The receive loop detects connection closure (via `ConnectionClosed` exception or normal loop exit)
2. `_handle_connection_lost()` is called, which:
   - Sets `_connected = False`
   - Cleans up the websocket
   - Notifies the client via `on_disconnect` callback
   - Triggers reconnection if enabled
3. Mark all channels as unsubscribed
4. Calculate backoff delay: `min(base * multiplier^attempt, max_delay)`
5. Add random jitter (0-25%)
6. Attempt reconnection
7. On success, re-subscribe to all channels

The receive loop handles connection closure in three ways:
- **`ConnectionClosed` exception**: Raised when websocket closes with an error code
- **Normal loop exit**: When websocket closes with code 1000/1001 (normal closure)
- **Other exceptions**: Treated as connection loss, triggers reconnection

Default parameters:
- Initial delay: 1 second
- Maximum delay: 30 seconds
- Multiplier: 2.0
- Max attempts: unlimited

## Threading Model

The library is single-threaded async. All operations run on the asyncio event loop. The main components:

- `_receive_loop`: Continuously reads from WebSocket
- `_keepalive_loop`: Monitors connection health
- `listen()`: User-facing blocking call

## Error Handling

Errors propagate as exceptions:

- `ConnectionError`: WebSocket connection issues
- `AuthenticationError`: Invalid HMAC signature
- `SubscriptionError`: Channel subscription rejected
- `ProtocolError`: Malformed message or unexpected event

The connection layer catches WebSocket errors and triggers reconnection if enabled.

## Testing

Unit tests cover:
- Message serialization/deserialization
- HMAC signature generation
- Channel type detection
- Configuration loading

Integration tests require a running Reverb server. These are not included in CI but can be run locally:

```bash
REVERB_HOST=localhost REVERB_PORT=8080 pytest tests/integration/
```

## Performance Considerations

- Message parsing is synchronous but fast (JSON decode)
- Event dispatch is async; slow handlers won't block receiving
- Reconnection uses asyncio.sleep, not blocking sleep
- No message buffering during disconnect (messages are lost)

## Extending

### Custom Channel Types

Subclass `Channel` and implement `_subscribe()`:

```python
class EncryptedChannel(PrivateChannel):
    def __init__(self, name, client, encryption_key):
        super().__init__(name, client)
        self.encryption_key = encryption_key

    async def _handle_event(self, event, data):
        decrypted = decrypt(data, self.encryption_key)
        await super()._handle_event(event, decrypted)
```

### Custom Authentication

Replace the authenticator on the client:

```python
class CustomAuthenticator:
    def authenticate(self, socket_id, channel_name, user_data=None):
        # Fetch auth token from your backend
        return {"auth": fetch_token(socket_id, channel_name)}

client._authenticator = CustomAuthenticator()
```
