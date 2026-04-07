#!/bin/bash
#
# Reverse configuration changes made by setup.sh and install_service.sh
#

echo "=== Stopping and removing simulation service ==="
if systemctl is-enabled jetsoncontrol-sim.service &>/dev/null; then
    sudo systemctl disable --now jetsoncontrol-sim.service
    echo "Simulation service disabled and stopped."
else
    echo "Simulation service not installed, skipping."
fi
sudo rm -f /etc/systemd/system/jetsoncontrol-sim.service

echo "=== Stopping and removing GPIO control service ==="
if systemctl is-enabled jetsoncontrol-gpio.service &>/dev/null; then
    sudo systemctl disable --now jetsoncontrol-gpio.service
    echo "GPIO service disabled and stopped."
else
    echo "GPIO service not installed, skipping."
fi
sudo rm -f /etc/systemd/system/jetsoncontrol-gpio.service

echo "=== Restoring LED ==="
if [ -w /sys/class/leds/mmc0/trigger ]; then
    echo mmc0 | sudo tee /sys/class/leds/mmc0/trigger > /dev/null
    echo "LED restored to mmc0."
fi

echo "=== Stopping and removing systemd service ==="
if systemctl is-enabled jetsoncontrol.service &>/dev/null; then
    sudo systemctl disable --now jetsoncontrol.service
    echo "Service disabled and stopped."
else
    echo "Service not installed, skipping."
fi
sudo rm -f /etc/systemd/system/jetsoncontrol.service
sudo systemctl daemon-reload

echo "=== Removing D-BUS config ==="
sudo rm -f /etc/dbus-1/system.d/wof2.jetsoncontrol.service.conf
sudo systemctl restart dbus.service

echo "=== Restoring Bluetooth service (re-enabling audio plugins) ==="
sudo rm -f /etc/systemd/system/bluetooth.service.d/jetsonbt.conf
sudo rmdir /etc/systemd/system/bluetooth.service.d 2>/dev/null || true
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
