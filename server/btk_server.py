#!/usr/bin/python3
#
# Bluetooth keyboard/Mouse emulator DBUS Service
#
# HID server only — no pairing logic.
# Run pair.py first to pair a host device, then use this server.
#

from __future__ import absolute_import, print_function
import os
import sys
import configparser
import dbus
import dbus.service
import dbus.mainloop.glib
import time
import socket
import threading
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop
import logging
from logging import debug, info, warning, error

logging.basicConfig(level=logging.DEBUG)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.ini")
config = configparser.ConfigParser()
config.read(CONFIG_PATH)

DEVICE_NAME = config.get("device", "name", fallback="RaspiControl")
DEVICE_CLASS = "0x002540"
AGENT_PATH = "/wof2/raspicontrol/agent"


class BTAgent(dbus.service.Object):
    """BlueZ Agent for handling reconnection authorization."""

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


def get_paired_devices():
    """Return list of paired Bluetooth device addresses via BlueZ D-BUS."""
    bus = dbus.SystemBus()
    manager = dbus.Interface(
        bus.get_object("org.bluez", "/"),
        "org.freedesktop.DBus.ObjectManager")

    paired = []
    for path, interfaces in manager.GetManagedObjects().items():
        device = interfaces.get("org.bluez.Device1")
        if device and device.get("Paired"):
            paired.append(str(device.get("Address", "unknown")))
    return paired


class BTKbDevice():
    P_CTRL = 17
    P_INTR = 19
    SDP_RECORD_PATH = sys.path[0] + "/sdp_record.xml"
    UUID = "00001124-0000-1000-8000-00805f9b34fb"

    def __init__(self):
        print("Setting up BT device")
        self.init_bt_device()
        self.init_bluez_profile()

    def init_bt_device(self):
        print("Configuring device name: " + DEVICE_NAME)
        os.system("hciconfig hci0 up")
        os.system("hciconfig hci0 name " + DEVICE_NAME)
        os.system("hciconfig hci0 piscan")

    def init_bluez_profile(self):
        print("Configuring Bluez Profile")
        service_record = self.read_sdp_service_record()
        opts = {
            "AutoConnect": True,
            "ServiceRecord": service_record
        }
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object(
            "org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
        manager.RegisterProfile("/org/bluez/hci0", BTKbDevice.UUID, opts)
        print("Profile registered")
        os.system("hciconfig hci0 class " + DEVICE_CLASS)

    def read_sdp_service_record(self):
        print("Reading service record")
        try:
            fh = open(BTKbDevice.SDP_RECORD_PATH, "r")
        except:
            sys.exit("Could not open the sdp record. Exiting...")
        return fh.read()

    def setup_socket(self):
        self.scontrol = socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.sinterrupt = socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.scontrol.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sinterrupt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.scontrol.bind((socket.BDADDR_ANY, self.P_CTRL))
        self.sinterrupt.bind((socket.BDADDR_ANY, self.P_INTR))

    def listen(self):
        print("\033[0;33mWaiting for connections\033[0m")

        self.setup_socket()
        self.scontrol.listen(5)
        self.sinterrupt.listen(5)

        self.ccontrol, cinfo = self.scontrol.accept()
        print(
            "\033[0;32mGot a connection on the control channel from %s\033[0m" % cinfo[0])

        self.cinterrupt, cinfo = self.sinterrupt.accept()
        print(
            "\033[0;32mGot a connection on the interrupt channel from %s\033[0m" % cinfo[0])

    def send_string(self, message):
        try:
            self.cinterrupt.send(bytes(message))
        except OSError as err:
            error(err)
            self.listen()


class BTKbService(dbus.service.Object):

    def __init__(self):
        print("Setting up service")
        bus_name = dbus.service.BusName(
            "wof2.raspicontrol.service", bus=dbus.SystemBus())
        dbus.service.Object.__init__(
            self, bus_name, "/wof2/raspicontrol/service")
        self.device = BTKbDevice()

        # Start listening in a thread so GLib mainloop can handle D-BUS
        self.connect_thread = threading.Thread(target=self._listen, daemon=True)
        self.connect_thread.start()

    def _listen(self):
        self.device.listen()
        print("\033[0;32mReady to send HID reports!\033[0m")

    @dbus.service.method('wof2.raspicontrol.service', in_signature='yay')
    def send_keys(self, modifier_byte, keys):
        print("Get send_keys request through dbus")
        print("key msg: ", keys)
        state = [0xA1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
        state[2] = int(modifier_byte)
        count = 4
        for key_code in keys:
            if(count < 10):
                state[count] = int(key_code)
            count += 1
        self.device.send_string(state)

    @dbus.service.method('wof2.raspicontrol.service', in_signature='yay')
    def send_mouse(self, modifier_byte, keys):
        state = [0xA1, 2, 0, 0, 0, 0]
        count = 2
        for key_code in keys:
            if(count < 6):
                state[count] = int(key_code)
            count += 1
        self.device.send_string(state)


if __name__ == "__main__":
    try:
        if not os.geteuid() == 0:
            sys.exit("Only root can run this script")

        DBusGMainLoop(set_as_default=True)

        # Check for paired devices
        paired = get_paired_devices()
        if not paired:
            print("\033[0;31mNo paired Bluetooth devices found.\033[0m")
            print("Run pair.py first to pair a host device:")
            print("  sudo python3 pair.py")
            sys.exit(1)
        print("Paired devices: %s" % ", ".join(paired))

        # Register agent for reconnection authorization
        bus = dbus.SystemBus()
        agent = BTAgent(bus, AGENT_PATH)
        agent_manager = dbus.Interface(
            bus.get_object("org.bluez", "/org/bluez"),
            "org.bluez.AgentManager1")
        agent_manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
        agent_manager.RequestDefaultAgent(AGENT_PATH)
        print("Agent registered")

        myservice = BTKbService()
        loop = GLib.MainLoop()
        loop.run()
    except KeyboardInterrupt:
        sys.exit()
