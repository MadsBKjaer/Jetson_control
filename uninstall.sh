#!/bin/bash
#
# Reverse configuration changes made by setup.sh
#

echo "=== Removing D-BUS config ==="
sudo rm -f /etc/dbus-1/system.d/wof2.raspicontrol.service.conf
sudo systemctl restart dbus.service

echo "=== Restoring Bluetooth service (re-enabling audio plugins) ==="
sudo sed -i '/^ExecStart=/ s/ --noplugin=[^ ]*//g' /lib/systemd/system/bluetooth.service
sudo systemctl daemon-reload
sudo systemctl restart bluetooth.service

echo "=== Removing all Bluetooth pairings ==="
for mac in $(bluetoothctl devices Paired 2>/dev/null | awk '{print $2}'); do
    echo "Removing $mac..."
    bluetoothctl remove "$mac"
done

echo ""
echo "=== Uninstall complete ==="
echo "Bluetooth is back to default configuration."
echo "Installed packages were kept. Remove manually if needed:"
echo "  sudo apt-get remove bluez-tools python3-dbus python3-pyudev python3-evdev python3-gi"
