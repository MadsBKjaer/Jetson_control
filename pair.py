#!/usr/bin/python3
#
# Bluetooth pairing script - No PIN required (SSP Just Works)
# Run this BEFORE btk_server.py to pair with Windows 10/11
#

import os
import sys
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop

AGENT_PATH = "/org/thanhle/btkbagent"
AGENT_CAPABILITY = "NoInputNoOutput"


class BTAgent(dbus.service.Object):
    """BlueZ Agent that auto-accepts pairing without PIN (SSP Just Works)."""

    def __init__(self, bus, path):
        dbus.service.Object.__init__(self, bus, path)

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Release(self):
        print("Agent: Released")

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        # Only allow HID-related services, reject audio profiles
        HID_UUIDS = [
            "00001124",  # HID
            "00001200",  # PnP Information
            "00001800",  # Generic Access
            "00001801",  # Generic Attribute
            "0000180a",  # Device Information
        ]
        uuid_prefix = uuid[:8].lower()
        if any(uuid_prefix == allowed for allowed in HID_UUIDS):
            print("Agent: AuthorizeService (%s, %s) -> ALLOWED" % (device, uuid))
            return
        print("Agent: AuthorizeService (%s, %s) -> REJECTED (non-HID)" % (device, uuid))
        raise dbus.exceptions.DBusException(
            "org.bluez.Error.Rejected",
            "Only HID services are allowed")

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        print("Agent: RequestPinCode (%s) -> '0000'" % device)
        return "0000"

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        print("Agent: RequestPasskey (%s) -> 0" % device)
        return dbus.UInt32(0)

    @dbus.service.method("org.bluez.Agent1", in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        print("Agent: DisplayPasskey (%s, %06u entered %u)" % (device, passkey, entered))

    @dbus.service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        print("Agent: RequestConfirmation (%s, %06d) -> auto-confirmed" % (device, passkey))

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        print("Agent: RequestAuthorization (%s) -> auto-authorized" % device)

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Cancel(self):
        print("Agent: Cancel")


SDP_RECORD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server", "sdp_record.xml")
HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"
# 0x002540 = Peripheral (keyboard+mouse combo), no Audio/Telephony bits
DEVICE_CLASS = "0x002540"


def enforce_device_class():
    """Force device class - BlueZ plugins keep overriding it."""
    os.system("hciconfig hci0 class " + DEVICE_CLASS)
    return True  # keep timer running


if __name__ == "__main__":
    if not os.geteuid() == 0:
        sys.exit("Only root can run this script")

    # Restart bluetooth with audio plugins disabled
    os.system("hciconfig hci0 down")
    os.system("systemctl stop bluetooth")
    import time
    time.sleep(1)
    os.system("/usr/libexec/bluetooth/bluetoothd --noplugin=input,audio,a2dp,avrcp,sap &")
    time.sleep(2)
    os.system("hciconfig hci0 up")
    os.system("hciconfig hci0 class " + DEVICE_CLASS)
    os.system("hciconfig hci0 name ThanhLe_Keyboard_Mouse")
    os.system("hciconfig hci0 piscan")

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    # Register HID profile with SDP record so Windows sees correct services
    try:
        with open(SDP_RECORD_PATH, "r") as fh:
            sdp_record = fh.read()
        profile_manager = dbus.Interface(
            bus.get_object("org.bluez", "/org/bluez"),
            "org.bluez.ProfileManager1")
        opts = {
            "AutoConnect": True,
            "ServiceRecord": sdp_record
        }
        profile_manager.RegisterProfile("/org/bluez/hci0", HID_UUID, opts)
        print("HID profile registered with SDP record")
    except Exception as e:
        print("Warning: could not register HID profile: %s" % e)

    # Force class after profile registration
    os.system("hciconfig hci0 class " + DEVICE_CLASS)

    # Register agent
    agent = BTAgent(bus, AGENT_PATH)
    agent_manager = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez"),
        "org.bluez.AgentManager1")
    agent_manager.RegisterAgent(AGENT_PATH, AGENT_CAPABILITY)
    agent_manager.RequestDefaultAgent(AGENT_PATH)
    print("Agent registered (NoInputNoOutput - no PIN required)")

    # Make device discoverable and pairable
    adapter = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez/hci0"),
        "org.freedesktop.DBus.Properties")
    adapter.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(True))
    adapter.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(0))
    adapter.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(True))
    adapter.Set("org.bluez.Adapter1", "PairableTimeout", dbus.UInt32(0))

    # Force class again and keep enforcing it every 2 seconds
    os.system("hciconfig hci0 class " + DEVICE_CLASS)
    GLib.timeout_add_seconds(2, enforce_device_class)

    # Verify
    os.system("hciconfig hci0 class")

    print("")
    print("Device is discoverable and pairable.")
    print("On Windows: Settings -> Bluetooth -> Add device -> find this RPi")
    print("Pairing will be accepted automatically (no PIN).")
    print("")
    print("Press Ctrl+C after pairing is done, then start btk_server.py")

    try:
        GLib.MainLoop().run()
    except KeyboardInterrupt:
        print("\nStopping pairing agent...")
        agent_manager.UnregisterAgent(AGENT_PATH)
        os.system("killall bluetoothd 2>/dev/null")
        os.system("systemctl start bluetooth")
