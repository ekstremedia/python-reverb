#!/bin/bash
echo "Restarting reverb-client service..."
sudo systemctl restart reverb-client
echo "Done. Showing status:"
sudo systemctl status reverb-client --no-pager
