#!/bin/bash
# Copy the local service files to systemd
sudo cp /home/valex92/sms-calendar-agent/sms-agent.service /etc/systemd/system/sms-agent.service
sudo cp /home/valex92/sms-calendar-agent/ngrok.service /etc/systemd/system/ngrok.service

# Reload systemd to recognize the new files
sudo systemctl daemon-reload

# Start and enable the main sms-agent service
sudo systemctl enable sms-agent
sudo systemctl restart sms-agent

# Start and enable the ngrok service
sudo systemctl enable ngrok
sudo systemctl restart ngrok

echo "Both sms-agent and ngrok services have been started and enabled on boot!"
echo "Check status with: sudo systemctl status sms-agent ngrok"