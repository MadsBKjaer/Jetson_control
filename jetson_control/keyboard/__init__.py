"""
Keyboard control module for Jetson Control.

Provides functions to send keyboard input via Bluetooth HID.
"""

import dbus
import dbus.service
import dbus.mainloop.glib
import time
from . import keymap


class KeyboardClient:
    """Client for sending keyboard input via DBUS to the Bluetooth HID server."""

    KEY_DOWN_TIME = 0.01
    KEY_DELAY = 0.01

    def __init__(self):
        # Initialize DBUS connection
        self.bus = dbus.SystemBus()
        self.btkservice = self.bus.get_object(
            'wof2.jetsoncontrol.service', '/wof2/jetsoncontrol/service')
        self.iface = dbus.Interface(self.btkservice, 'wof2.jetsoncontrol.service')

        # Keyboard state structure
        self.state = [
            0xA1,  # input report
            0x01,  # keyboard
            [0, 0, 0, 0, 0, 0, 0, 0],  # modifiers
            0x00,  # reserved
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00  # keys
        ]

        # Scancode mappings for special characters
        self.scancodes = {
            " ": "KEY_SPACE",
            "!": "KEY_1",
            "@": "KEY_2",
            "#": "KEY_3",
            "$": "KEY_4",
            "%": "KEY_5",
            "^": "KEY_6",
            "&": "KEY_7",
            "*": "KEY_8",
            "(": "KEY_9",
            ")": "KEY_0",
            "-": "KEY_MINUS",
            "_": "KEY_MINUS",
            "=": "KEY_EQUAL",
            "+": "KEY_EQUAL",
            "[": "KEY_LEFTBRACE",
            "{": "KEY_LEFTBRACE",
            "]": "KEY_RIGHTBRACE",
            "}": "KEY_RIGHTBRACE",
            ";": "KEY_SEMICOLON",
            ":": "KEY_SEMICOLON",
            "'": "KEY_APOSTROPHE",
            "\"": "KEY_APOSTROPHE",
            "`": "KEY_GRAVE",
            "~": "KEY_GRAVE",
            "\\": "KEY_BACKSLASH",
            "|": "KEY_BACKSLASH",
            ",": "KEY_COMMA",
            "<": "KEY_COMMA",
            ".": "KEY_DOT",
            ">": "KEY_DOT",
            "/": "KEY_SLASH",
            "?": "KEY_SLASH"
        }

    def send_string(self, string_to_send):
        """Send a string of text as keyboard input."""
        for c in string_to_send:
            cu = c.upper()
            modifiers = [0, 0, 0, 0, 0, 0, 0, 0]
            if cu in self.scancodes:
                scantablekey = self.scancodes[cu]
                if scantablekey.islower():
                    modifiers = [0, 0, 0, 0, 0, 0, 1, 0]
                    scantablekey = scantablekey.upper()
            else:
                if c.isupper():
                    modifiers = [0, 0, 0, 0, 0, 0, 1, 0]
                scantablekey = "KEY_" + cu

            try:
                scancode = keymap.keytable[scantablekey]
            except KeyError:
                print("character not found in keytable:", c)
                continue
            else:
                self.send_key_down(scancode, modifiers)
                time.sleep(self.KEY_DOWN_TIME)
                self.send_key_up()
                time.sleep(self.KEY_DELAY)

    def send_key_down(self, scancode, modifiers):
        """Send a key down event."""
        self.state[2] = modifiers
        self.state[4] = scancode
        self.send_key_state()

    def send_key_up(self):
        """Send a key up event."""
        self.state[4] = 0
        self.send_key_state()

    def send_key_state(self):
        """Send the current key state."""
        bin_str = "".join(map(str, self.state[2]))
        self.iface.send_keys(int(bin_str, 2), self.state[4:10])


# Global client instance
_client = None

def send_string(text):
    """Send a string of text as keyboard input.

    Args:
        text (str): The text to send
    """
    global _client
    if _client is None:
        _client = KeyboardClient()
    _client.send_string(text)

def send_key(scancode, modifiers=None):
    """Send a single key press.

    Args:
        scancode (int): HID key code
        modifiers (list, optional): List of 8 modifier bits
    """
    global _client
    if _client is None:
        _client = KeyboardClient()
    if modifiers is None:
        modifiers = [0, 0, 0, 0, 0, 0, 0, 0]
    _client.send_key_down(scancode, modifiers)
    time.sleep(_client.KEY_DOWN_TIME)
    _client.send_key_up()
    time.sleep(_client.KEY_DELAY)