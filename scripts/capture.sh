#!/bin/bash
#
# Capture script - sends the latest image to Laravel
#
# Environment variables (from device_listener.py):
#   DEVICE_ID     - Camera ID (e.g., kringelen_01)
#   API_BASE_URL  - Base URL (e.g., https://ekstremedia.no)
#   REQUEST_ID    - Request identifier
#
# Required in .env:
#   API_TOKEN     - Bearer token for authentication
#
# Image directory structure expected:
#   /var/www/html/images/YYYY/MM/DD/*.jpg
#

set -e

# Configuration
IMAGE_BASE_PATH="${IMAGE_BASE_PATH:-/var/www/html/images}"
UPLOAD_ENDPOINT="${API_BASE_URL}/api/camera/current-image"

# Load token from .env if not already set
if [ -z "$API_TOKEN" ]; then
    # Try to source from the same directory as the script
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    if [ -f "$SCRIPT_DIR/../.env" ]; then
        export $(grep -E '^API_TOKEN=' "$SCRIPT_DIR/../.env" | xargs)
    fi
fi

if [ -z "$API_TOKEN" ]; then
    echo "Error: API_TOKEN not set" >&2
    exit 1
fi

if [ -z "$DEVICE_ID" ]; then
    echo "Error: DEVICE_ID not set" >&2
    exit 1
fi

# Today's date
YEAR=$(date +"%Y")
MONTH=$(date +"%m")
DAY=$(date +"%d")

# Construct today's directory path
TODAY_PATH="${IMAGE_BASE_PATH}/${YEAR}/${MONTH}/${DAY}"

# Check if directory exists
if [ ! -d "$TODAY_PATH" ]; then
    echo "Error: Image directory not found: $TODAY_PATH" >&2
    exit 1
fi

# Get the most recent photo
LATEST_PHOTO=$(ls -t "${TODAY_PATH}"/*.jpg 2>/dev/null | head -n 1)

if [ -z "$LATEST_PHOTO" ] || [ ! -f "$LATEST_PHOTO" ]; then
    echo "Error: No images found in $TODAY_PATH" >&2
    exit 1
fi

# Upload the image
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    -H "Authorization: Bearer $API_TOKEN" \
    -F "image=@$LATEST_PHOTO" \
    -F "camera_id=$DEVICE_ID" \
    -F "request_id=$REQUEST_ID" \
    "$UPLOAD_ENDPOINT")

# Extract HTTP status code (last line)
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "$LATEST_PHOTO"
    exit 0
else
    echo "Error: Upload failed with status $HTTP_CODE: $BODY" >&2
    exit 1
fi
