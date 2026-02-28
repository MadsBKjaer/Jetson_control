#!/bin/bash
set -e

echo "=== Installing dependencies ==="
sudo apt-get update -y
sudo apt-get install -y --ignore-missing bluez bluez-tools python3 python3-dbus python3-pyudev python3-evdev python3-gi

echo "=== Configuring D-BUS permissions ==="
sudo cp dbus/wof2.raspicontrol.service.conf /etc/dbus-1/system.d
sudo systemctl restart dbus.service

echo "=== Configuring Bluetooth service (disabling audio plugins) ==="
sudo mkdir -p /etc/systemd/system/bluetooth.service.d
sudo tee /etc/systemd/system/bluetooth.service.d/raspibt.conf > /dev/null <<EOF
[Service]
ExecStart=
ExecStart=/usr/libexec/bluetooth/bluetoothd --compat --noplugin=sap,input,a2dp,avrcp,network,hfp,hsp
EOF
sudo systemctl daemon-reload
sudo systemctl restart bluetooth.service

echo ""
echo "=== Setup complete ==="
echo "Start the server:  sudo python3 server/btk_server.py"
echo "Or install as service:  sudo ./install_service.sh"
