#!/bin/bash
echo "=== Showing Live Logs ==="
echo "Press Ctrl+C to exit."
echo "-------------------------"

# We can use journalctl to tail multiple services at once!
sudo journalctl -u sms-agent -u ngrok -f
