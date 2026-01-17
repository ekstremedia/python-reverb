# Raspberry Pi Setup Guide

This guide covers deploying python-reverb on a Raspberry Pi to create a device that responds to commands from your Laravel Reverb server.

## Quick Start

1. Clone the repo
2. Configure `.env` with your device ID and credentials
3. Run `device_listener.py`

No device-specific Python files needed.

## Architecture

```
┌─────────────────────┐      WebSocket       ┌─────────────────────┐
│   Laravel Server    │◄────────────────────►│   Reverb Server     │
│   (your-server.com) │                      │   (port 443)        │
└─────────────────────┘                      └─────────────────────┘
         │                                            ▲
         │ HTTP POST                                  │ WebSocket
         │ /api/device/{id}/ping                      │
         ▼                                            │
┌─────────────────────┐                      ┌─────────────────────┐
│   Broadcast Event   │─────────────────────►│   Raspberry Pi      │
│   DeviceHealthPing  │   channel:           │   (DEVICE_ID)       │
└─────────────────────┘   device.{id}        └─────────────────────┘
                                                      │
         ┌────────────────────────────────────────────┘
         │ HTTP POST /api/device/pong
         ▼
┌─────────────────────┐
│   Broadcast Event   │──────► Frontend subscribers
│   DeviceHealthPong  │        (device-responses channel)
└─────────────────────┘
```

## Flow

1. Admin/User calls `POST /api/device/{device_id}/ping`
2. Laravel broadcasts `DeviceHealthPing` event to channel `device.{device_id}`
3. Raspberry Pi receives the event via WebSocket
4. Raspberry Pi collects system metrics (load, memory, CPU temp, uptime)
5. Raspberry Pi calls `POST /api/device/pong` with metrics
6. Laravel broadcasts `DeviceHealthPong` for frontend listeners

## Prerequisites

- Raspberry Pi with Raspberry Pi OS (Debian-based)
- Python 3.9 or later
- Network access to your Reverb server
- SSH access to the Pi

## Installation

### 1. SSH into your Raspberry Pi

```bash
ssh pi@kringelen_01.local
# or
ssh pi@192.168.1.x
```

### 2. Install Python and venv

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

### 3. Clone the repository

```bash
cd /home/pi
git clone https://github.com/terje/python-reverb.git
cd python-reverb
```

### 4. Create virtual environment and install

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install . aiohttp
```

### 5. Create configuration file

Copy the example and edit:

```bash
cp .env.example .env
nano .env
```

Configure with your values:

```bash
# Device Configuration
DEVICE_ID=my-device-name

# Reverb Server
REVERB_APP_KEY=your-reverb-app-key
REVERB_APP_SECRET=your-reverb-app-secret
REVERB_HOST=your-server.com
REVERB_PORT=443
REVERB_SCHEME=wss

# API endpoint for pong responses
API_BASE_URL=https://your-server.com

# Logging (DEBUG, INFO, WARNING, ERROR)
REVERB_LOG_LEVEL=INFO
```

Get credentials from your Laravel `.env` file (`REVERB_APP_KEY`, `REVERB_APP_SECRET`).

### 6. Test the connection

```bash
source venv/bin/activate
python device_listener.py
```

You should see:

```
2026-01-17 12:00:00,000 INFO device.my-device-name: starting device_id=my-device-name
2026-01-17 12:00:00,000 INFO device.my-device-name: api_base_url=https://your-server.com
2026-01-17 12:00:00,100 INFO reverb.connection: Connected with socket_id: 416200246.685575608
2026-01-17 12:00:00,100 INFO device.my-device-name: connected socket_id=416200246.685575608
2026-01-17 12:00:00,150 INFO device.my-device-name: listening on channel device.my-device-name
```

### 7. Test with a ping

From another terminal or your server:

```bash
curl -X POST https://your-server.com/api/device/my-device-name/ping
```

The Pi should log:

```
INFO device.my-device-name: health ping received request_id=833bee71-5291-44a7-8687-96f938f0a55e
INFO device.my-device-name: pong sent request_id=833bee71-5291-44a7-8687-96f938f0a55e metrics={...}
```

Press `Ctrl+C` to stop the test.

## Running as a System Service

### 1. Create the systemd service file

```bash
sudo tee /etc/systemd/system/reverb-client.service << 'EOF'
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
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

### 2. Enable and start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable reverb-client
sudo systemctl start reverb-client
```

### 3. Check status

```bash
sudo systemctl status reverb-client
```

### 4. View logs

```bash
# Follow logs in real-time
sudo journalctl -u reverb-client -f

# View last 100 lines
sudo journalctl -u reverb-client -n 100

# View logs since boot
sudo journalctl -u reverb-client -b
```

### 5. Restart after changes

```bash
sudo systemctl restart reverb-client
```

## Extending the Device Script

The `device_listener.py` script handles health pings out of the box. For custom commands, you have two options:

### Option 1: Fork and customize

Copy `device_listener.py` to your own file and modify the `_on_command` method:

```python
async def _on_command(self, event: str, data: Any, channel: str | None) -> None:
    action = data.get("action")
    params = data.get("params", {})

    if action == "capture_image":
        await self._capture_image(params)
    elif action == "upload_images":
        await self._upload_images(params)
```

### Option 2: External scripts

Place scripts in `/opt/scripts/` that can be triggered via your Laravel backend:

```bash
sudo mkdir -p /opt/scripts
sudo chown pi:pi /opt/scripts

cat > /opt/scripts/capture.sh << 'EOF'
#!/bin/bash
raspistill -o /tmp/capture.jpg
EOF
chmod +x /opt/scripts/capture.sh
```

## Multiple Devices

Each device uses its own `DEVICE_ID` from `.env`. The generic workflow:

1. Clone repo on each device
2. Configure `.env` with unique `DEVICE_ID`
3. Run `device_listener.py`

```bash
# Device 1 .env
DEVICE_ID=camera-north

# Device 2 .env
DEVICE_ID=camera-south

# Device 3 .env
DEVICE_ID=sensor-garage
```

All devices use the same `device_listener.py` script.

## Troubleshooting

### Connection refused

Check that:
- Reverb server is running on your Laravel server
- Port 443 (or your configured port) is accessible
- Credentials match your Laravel `.env`

### SSL certificate errors

If using self-signed certificates:

```bash
# In .env
REVERB_SCHEME=ws
REVERB_PORT=8080
```

### Service won't start

Check logs:

```bash
sudo journalctl -u reverb-client -n 50 --no-pager
```

Common issues:
- Missing dependencies: `pip install . aiohttp`
- Wrong Python path: Update `ExecStart` in service file
- Permission issues: Ensure `pi` user owns the directory

### High memory usage

The script is lightweight but if memory is constrained:

```bash
# Check memory usage
ps aux | grep python

# Limit in systemd
sudo systemctl edit reverb-client
# Add:
# [Service]
# MemoryMax=100M
```

## Security Considerations

1. Keep `.env` file permissions restricted:
   ```bash
   chmod 600 /home/pi/python-reverb/.env
   ```

2. Use HTTPS/WSS in production (default)

3. Rotate Reverb credentials periodically

4. Consider using private channels for sensitive commands:
   ```python
   channel = await client.subscribe(f"private-device.{DEVICE_ID}")
   ```

## Updating

```bash
cd /home/pi/python-reverb
git pull
source venv/bin/activate
pip install . --upgrade
sudo systemctl restart reverb-client
```
