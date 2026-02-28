#!/usr/bin/python3
#
# Bluetooth keyboard/Mouse emulator DBUS Service
#
# Handles both pairing and HID serving in one process.
# Usage: sudo python3 btk_server.py
#

from __future__ import absolute_import, print_function
import os
import sys
import signal
import subprocess
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
    """BlueZ Agent — auto-accepts pairing, rejects non-HID profiles."""

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


def cleanup_before_start():
    """Kill old btk_server instances and ensure bluetoothd is in clean state."""
    my_pid = os.getpid()

    # Build set of PIDs to never kill: self + all ancestors up to init
    protected = set()
    pid = my_pid
    while pid > 1:
        protected.add(pid)
        try:
            with open("/proc/%d/stat" % pid) as f:
                pid = int(f.read().split(")")[1].split()[1])
        except (IOError, IndexError, ValueError):
            break
    protected.add(1)

    # Kill old btk_server.py python processes (excluding self and ancestors)
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "python.*btk_server"], text=True).strip()
        for pid_str in out.split("\n"):
            pid = int(pid_str)
            if pid not in protected:
                print("Killing old btk_server.py (PID %d)" % pid)
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        time.sleep(1)
        # Force-kill any survivors
        out = subprocess.check_output(
            ["pgrep", "-f", "python.*btk_server"], text=True).strip()
        for pid_str in out.split("\n"):
            pid = int(pid_str)
            if pid not in protected:
                print("Force-killing old btk_server.py (PID %d)" % pid)
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        time.sleep(0.5)
    except (subprocess.CalledProcessError, ValueError):
        pass  # No old processes found

    # Trust all paired devices
    try:
        bus = dbus.SystemBus()
        manager = dbus.Interface(
            bus.get_object("org.bluez", "/"),
            "org.freedesktop.DBus.ObjectManager")
        for path, interfaces in manager.GetManagedObjects().items():
            dev = interfaces.get("org.bluez.Device1")
            if dev and dev.get("Paired") and not dev.get("Trusted"):
                props = dbus.Interface(
                    bus.get_object("org.bluez", path),
                    "org.freedesktop.DBus.Properties")
                props.Set("org.bluez.Device1", "Trusted", True)
                print("Trusted: %s" % dev.get("Address", "unknown"))
    except dbus.exceptions.DBusException as e:
        print("Warning: could not set trusted: %s" % e)


def register_profile_with_retry(service_record):
    """Register HID profile, retrying if UUID is stale from a crashed process."""
    opts = {
        "AutoConnect": True,
        "ServiceRecord": service_record
    }

    for i in range(10):
        try:
            bus = dbus.SystemBus()
            manager = dbus.Interface(bus.get_object(
                "org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
            manager.RegisterProfile("/org/bluez/hci0",
                                    BTKbDevice.UUID, opts)
            print("Profile registered")
            return
        except dbus.exceptions.DBusException as e:
            if "UUID already registered" not in str(e):
                raise
            if i == 0:
                print("UUID already registered, waiting for release...")
            time.sleep(1)

    raise RuntimeError("Could not register HID profile after 10 attempts")


def enable_discoverability():
    """Make adapter discoverable and pairable so new devices can pair anytime."""
    try:
        bus = dbus.SystemBus()
        adapter = dbus.Interface(
            bus.get_object("org.bluez", "/org/bluez/hci0"),
            "org.freedesktop.DBus.Properties")
        adapter.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(True))
        adapter.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(0))
        adapter.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(True))
        adapter.Set("org.bluez.Adapter1", "PairableTimeout", dbus.UInt32(0))
        print("Discoverable and pairable enabled")
    except dbus.exceptions.DBusException as e:
        print("Warning: could not set discoverable: %s" % e)


def nudge_hosts(paired_addrs):
    """Nudge paired hosts to reconnect by creating ACL link (slave role)."""
    time.sleep(3)  # Wait for L2CAP sockets to be listening
    for addr in paired_addrs:
        print("Nudging %s to reconnect..." % addr)
        try:
            subprocess.run(["hcitool", "cc", "--role=s", addr],
                           capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            pass
        print("Nudge sent to %s" % addr)


class BTKbDevice():
    P_CTRL = 17
    P_INTR = 19
    SDP_RECORD_PATH = sys.path[0] + "/sdp_record.xml"
    UUID = "00001124-0000-1000-8000-00805f9b34fb"

    def __init__(self):
        print("Setting up BT device")
        self.scontrol = None
        self.sinterrupt = None
        self.ccontrol = None
        self.cinterrupt = None
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
        register_profile_with_retry(service_record)
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
        """Accept one HID connection (blocks until a host connects)."""
        # Close old client connections only
        for attr in ('ccontrol', 'cinterrupt'):
            sock = getattr(self, attr, None)
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
                setattr(self, attr, None)

        # Setup listening sockets if not already bound
        if not self.scontrol:
            print("\033[0;33mWaiting for connections\033[0m")
            for attempt in range(5):
                try:
                    self.setup_socket()
                    break
                except OSError as e:
                    if attempt < 4:
                        print("Port busy, retrying in 2s... (%s)" % e)
                        time.sleep(2)
                    else:
                        raise
            self.scontrol.listen(5)
            self.sinterrupt.listen(5)
        else:
            print("\033[0;33mWaiting for reconnection\033[0m")

        self.ccontrol, cinfo = self.scontrol.accept()
        print(
            "\033[0;32mGot a connection on the control channel from %s\033[0m" % cinfo[0])

        self.cinterrupt, cinfo = self.sinterrupt.accept()
        print(
            "\033[0;32mGot a connection on the interrupt channel from %s\033[0m" % cinfo[0])

        # Trust newly connected device
        addr = cinfo[0]
        try:
            dev_path = "/org/bluez/hci0/dev_" + addr.replace(":", "_")
            bus = dbus.SystemBus()
            props = dbus.Interface(
                bus.get_object("org.bluez", dev_path),
                "org.freedesktop.DBus.Properties")
            if not props.Get("org.bluez.Device1", "Trusted"):
                props.Set("org.bluez.Device1", "Trusted", True)
                print("Trusted: %s" % addr)
        except dbus.exceptions.DBusException:
            pass

    def wait_for_disconnect(self):
        """Block until the HID client disconnects."""
        try:
            while True:
                data = self.ccontrol.recv(1024)
                if not data:
                    break
        except OSError:
            pass
        print("\033[0;31mClient disconnected\033[0m")

    def send_string(self, message):
        try:
            self.cinterrupt.send(bytes(message))
        except OSError as err:
            error(err)


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
        """Listen loop — reconnects automatically on disconnect."""
        while True:
            try:
                self.device.listen()

                # Verify connection is stable (Windows reconnects multiple
                # times during HID driver setup)
                time.sleep(2)
                try:
                    self.device.ccontrol.getpeername()
                except OSError:
                    print("Connection dropped during setup, retrying...")
                    continue

                print("\033[0;32mReady to send HID reports!\033[0m")
                self.device.wait_for_disconnect()
            except Exception as e:
                print("\033[0;31m_listen error: %s\033[0m" % e, flush=True)
                import traceback
                traceback.print_exc()
                time.sleep(2)

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

        # Clean up stale state from previous runs
        cleanup_before_start()

        # Check for paired devices
        paired = get_paired_devices()
        if paired:
            print("Paired devices: %s" % ", ".join(paired))
        else:
            print("No paired devices — waiting for first pairing...")

        # Register agent for pairing and reconnection
        bus = dbus.SystemBus()
        agent = BTAgent(bus, AGENT_PATH)
        agent_manager = dbus.Interface(
            bus.get_object("org.bluez", "/org/bluez"),
            "org.bluez.AgentManager1")
        agent_manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
        agent_manager.RequestDefaultAgent(AGENT_PATH)
        print("Agent registered")

        myservice = BTKbService()

        # Enable discoverable/pairable so new devices can pair anytime
        enable_discoverability()

        # Nudge paired hosts to reconnect (needed after reboot)
        if paired:
            threading.Thread(target=nudge_hosts, args=(paired,), daemon=True).start()

        print("")
        print("On your host: Settings -> Bluetooth -> Add device -> find '%s'" % DEVICE_NAME)
        print("")

        loop = GLib.MainLoop()
        loop.run()
    except KeyboardInterrupt:
        print("\nInterrupted, exiting.")
        sys.exit(0)
    except Exception as e:
        print("\033[0;31mFATAL: %s\033[0m" % e, flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
