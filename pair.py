#!/usr/bin/python3
#
# Standalone pairing script.
# Run this once to pair a host device (Windows/macOS/Linux/Android).
# The HID profile + SDP record must be visible during pairing so the
# host recognises the RPi as a keyboard/mouse.
#
# After pairing, stop this script and use btk_server.py (or the
# systemd service) for day-to-day operation.
#

from __future__ import absolute_import, print_function
import os
import sys
import configparser
import dbus
import dbus.service
import dbus.mainloop.glib
import socket
import threading
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")
config = configparser.ConfigParser()
config.read(CONFIG_PATH)

DEVICE_NAME = config.get("device", "name", fallback="RaspiControl")
AGENT_PATH = "/wof2/raspicontrol/agent"
DEVICE_CLASS = "0x002540"
SDP_RECORD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server", "sdp_record.xml")
HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"


class BTAgent(dbus.service.Object):
    """BlueZ Agent - auto-accepts pairing, rejects audio profiles."""

    def __init__(self, bus, path):
        dbus.service.Object.__init__(self, bus, path)

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Release(self):
        print("Agent: Released")

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        ALLOWED = ["00001124", "00001200", "00001800", "00001801", "0000180a"]
        prefix = uuid[:8].lower()
        if any(prefix == a for a in ALLOWED):
            print("Agent: AuthorizeService (%s, %s) -> ALLOWED" % (device, uuid))
            return
        print("Agent: AuthorizeService (%s, %s) -> REJECTED" % (device, uuid))
        raise dbus.exceptions.DBusException(
            "org.bluez.Error.Rejected", "Only HID services allowed")

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        print("Agent: RequestPinCode -> '0000'")
        return "0000"

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        print("Agent: RequestPasskey -> 0")
        return dbus.UInt32(0)

    @dbus.service.method("org.bluez.Agent1", in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        print("Agent: DisplayPasskey (%06u)" % passkey)

    @dbus.service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        print("Agent: RequestConfirmation (%06d) -> confirmed" % passkey)

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        print("Agent: RequestAuthorization -> authorized")

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Cancel(self):
        print("Agent: Cancel")


def read_sdp_record():
    try:
        with open(SDP_RECORD_PATH, "r") as fh:
            return fh.read()
    except FileNotFoundError:
        sys.exit("Could not open %s" % SDP_RECORD_PATH)


def register_hid_profile(bus):
    service_record = read_sdp_record()
    opts = {
        "AutoConnect": True,
        "ServiceRecord": service_record,
    }
    manager = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez"),
        "org.bluez.ProfileManager1")
    manager.RegisterProfile("/org/bluez/hci0", HID_UUID, opts)
    print("HID profile registered")


def listen_l2cap():
    """Listen for L2CAP connections in background so pairing completes."""
    P_CTRL, P_INTR = 17, 19
    scontrol = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
    sinterrupt = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
    scontrol.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sinterrupt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    scontrol.bind((socket.BDADDR_ANY, P_CTRL))
    sinterrupt.bind((socket.BDADDR_ANY, P_INTR))
    scontrol.listen(5)
    sinterrupt.listen(5)

    print("L2CAP listening on PSM %d and %d..." % (P_CTRL, P_INTR))

    ccontrol, cinfo = scontrol.accept()
    print("\033[0;32mControl channel connected from %s\033[0m" % cinfo[0])

    cinterrupt, cinfo = sinterrupt.accept()
    print("\033[0;32mInterrupt channel connected from %s\033[0m" % cinfo[0])
    print("\033[0;32mPairing complete! You can now stop this script (Ctrl+C).\033[0m")
    print("Then start the HID server:  sudo python3 server/btk_server.py")
    print("Or install as a service:    sudo ./install_service.sh")

    # Keep sockets open until script exits
    try:
        while True:
            import time
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        ccontrol.close()
        cinterrupt.close()
        scontrol.close()
        sinterrupt.close()


if __name__ == "__main__":
    if not os.geteuid() == 0:
        sys.exit("Only root can run this script")

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    # Configure adapter
    print("Configuring Bluetooth adapter...")
    os.system("hciconfig hci0 up")
    os.system("hciconfig hci0 name " + DEVICE_NAME)
    os.system("hciconfig hci0 piscan")

    # Register HID profile (Windows needs to see it during pairing)
    register_hid_profile(bus)
    os.system("hciconfig hci0 class " + DEVICE_CLASS)

    # Register pairing agent
    agent = BTAgent(bus, AGENT_PATH)
    agent_manager = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez"),
        "org.bluez.AgentManager1")
    agent_manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
    agent_manager.RequestDefaultAgent(AGENT_PATH)
    print("Agent registered (NoInputNoOutput - no PIN required)")

    # Make discoverable and pairable
    adapter = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez/hci0"),
        "org.freedesktop.DBus.Properties")
    adapter.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(True))
    adapter.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(0))
    adapter.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(True))
    adapter.Set("org.bluez.Adapter1", "PairableTimeout", dbus.UInt32(0))

    # Force device class again after BlueZ operations
    os.system("hciconfig hci0 class " + DEVICE_CLASS)

    # Start L2CAP listener in background thread
    listen_thread = threading.Thread(target=listen_l2cap, daemon=True)
    listen_thread.start()

    print("")
    print("\033[0;33mWaiting for pairing...\033[0m")
    print("On your host: Settings -> Bluetooth -> Add device -> find '%s'" % DEVICE_NAME)
    print("Press Ctrl+C to exit.")
    print("")

    try:
        loop = GLib.MainLoop()
        loop.run()
    except KeyboardInterrupt:
        print("\nExiting.")
