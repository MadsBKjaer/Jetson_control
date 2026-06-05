#!/bin/bash
set -e

echo "=== Installing dependencies ==="
sudo apt-get update -y
sudo apt-get install -y --ignore-missing bluez bluez-tools python3 python3-dbus python3-pyudev python3-evdev python3-gi python3-jetson-gpio

echo "=== Configuring D-BUS permissions ==="
sudo cp dbus/wof2.jetsoncontrol.service.conf /etc/dbus-1/system.d
sudo systemctl restart dbus.service

echo "=== Configuring Bluetooth service (disabling audio plugins) ==="
sudo mkdir -p /etc/systemd/system/bluetooth.service.d
sudo rm -f /etc/systemd/system/bluetooth.service.d/jetsonbt.conf
sudo rm -f /etc/systemd/system/bluetooth.service.d/99-jetsonbt.conf
sudo tee /etc/systemd/system/bluetooth.service.d/zz-jetsonbt.conf > /dev/null <<EOF
[Service]
ExecStart=
ExecStart=/usr/lib/bluetooth/bluetoothd --compat -E --noplugin=sap,input,audio,a2dp,avrcp,network,hfp,hsp
EOF
sudo systemctl daemon-reload

echo "=== Setting Device Class natively in BlueZ ==="
sudo sed -i 's/^#*Class =.*/Class = 0x0025C0/' /etc/bluetooth/main.conf

sudo systemctl restart bluetooth.service

echo ""
echo "=== Setup complete ==="
echo "Start the server:  sudo python3 server/btk_server.py"
echo "Or install as service:  sudo ./install_service.sh"
