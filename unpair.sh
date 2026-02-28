#!/bin/bash
#
# Remove all paired Bluetooth devices from Raspberry Pi
# Use when you need to re-pair with a host
#

DEVICES=$(bluetoothctl devices Paired 2>/dev/null | awk '{print $2}')

if [ -z "$DEVICES" ]; then
    echo "No paired devices found."
    exit 0
fi

echo "Paired devices:"
bluetoothctl devices Paired
echo ""

for mac in $DEVICES; do
    echo "Removing $mac..."
    bluetoothctl remove "$mac"
done

echo ""
echo "All paired devices removed. You can now re-pair from your host."
