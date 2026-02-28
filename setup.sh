#!/bin/bash
set -e

echo "=== Installing dependencies ==="
sudo apt-get update -y
sudo apt-get install -y --ignore-missing bluez bluez-tools python3 python3-dbus python3-pyudev python3-evdev python3-gi

echo "=== Configuring D-BUS permissions ==="
sudo cp dbus/wof2.raspicontrol.service.conf /etc/dbus-1/system.d
sudo systemctl restart dbus.service

echo "=== Configuring Bluetooth service (disabling audio plugins) ==="
sudo sed -i '/^ExecStart=/ s/ --noplugin=[^ ]*//g' /lib/systemd/system/bluetooth.service
sudo sed -i '/^ExecStart=/ s/$/ --noplugin=input,audio,a2dp,avrcp,sap/' /lib/systemd/system/bluetooth.service
sudo systemctl daemon-reload
sudo systemctl restart bluetooth.service

echo ""
echo "=== Setup complete ==="
echo "Edit config.ini with your host's Bluetooth MAC address, then:"
echo "  1. Pair your device:  sudo python3 pair.py"
echo "  2. Start HID server:  sudo python3 server/btk_server.py"
