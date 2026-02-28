#!/bin/bash
set -e

SERVICE_NAME="raspicontrol"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Installing ${SERVICE_NAME} systemd service ==="
echo "Project directory: ${PROJECT_DIR}"

sudo tee "${SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=RaspiControl Bluetooth HID Server
After=bluetooth.service
Requires=bluetooth.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${PROJECT_DIR}/server/btk_server.py
WorkingDirectory=${PROJECT_DIR}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.service"
sudo systemctl start "${SERVICE_NAME}.service"

echo ""
echo "=== Service installed and started ==="
echo "Check status:  sudo systemctl status ${SERVICE_NAME}"
echo "View logs:     sudo journalctl -u ${SERVICE_NAME} -f"
echo "Stop:          sudo systemctl stop ${SERVICE_NAME}"
echo "Disable:       sudo systemctl disable ${SERVICE_NAME}"
