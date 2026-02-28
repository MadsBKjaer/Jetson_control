#!/bin/bash
sudo apt-get update -y
sudo apt-get install -y --ignore-missing git tmux bluez bluez-tools bluez-firmware
sudo apt-get install -y --ignore-missing python3 python3-dev python3-pip python3-dbus python3-pyudev python3-evdev python3-gi

sudo apt-get install -y libbluetooth-dev

sudo cp dbus/org.thanhle.btkbservice.conf /etc/dbus-1/system.d
sudo systemctl restart dbus.service

# Remove any existing --noplugin flags, then add the correct one
sudo sed -i '/^ExecStart=/ s/ --noplugin=[^ ]*//g' /lib/systemd/system/bluetooth.service
sudo sed -i '/^ExecStart=/ s/$/ --noplugin=input,audio,a2dp,avrcp,sap/' /lib/systemd/system/bluetooth.service
sudo systemctl daemon-reload
sudo systemctl restart bluetooth.service
