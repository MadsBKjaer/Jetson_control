#!/bin/bash
#
# Remove all paired Bluetooth devices from Jetson
# Use when you need to re-pair with a host
#

DEVICES=$(bluetoothctl paired-devices | awk '{print $2}')

if [ -z "$DEVICES" ]; then
    echo "No paired devices found."
    exit 0
fi

echo "Paired devices:"
bluetoothctl paired-devices
echo ""

for mac in $DEVICES; do
    echo "Removing $mac..."
    bluetoothctl remove "$mac"
done

echo ""
echo "All paired devices removed. You can now re-pair from your host."
