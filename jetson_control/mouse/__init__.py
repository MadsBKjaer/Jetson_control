"""
Mouse control module for Jetson Control.

Provides functions to send mouse input via Bluetooth HID.
"""

import dbus
import configparser
import os


class MouseClient:
    """Client for sending mouse input via DBUS to the Bluetooth HID server."""

    def __init__(self):
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.ini")
        config = configparser.ConfigParser()
        config.read(config_path)
        self.swap_buttons = config.getboolean("mouse", "swap_buttons", fallback=False)

        # Initialize DBUS
        self.bus = dbus.SystemBus()
        self.btkservice = self.bus.get_object(
            'wof2.jetsoncontrol.service', '/wof2/jetsoncontrol/service')
        self.iface = dbus.Interface(self.btkservice, 'wof2.jetsoncontrol.service')

    def send_mouse(self, buttons, dx, dy, dz):
        """Send mouse movement and button state.

        Args:
            buttons (int): Button bitmask (1=left, 2=right, 4=middle)
            dx (int): X movement (-127 to 127)
            dy (int): Y movement (-127 to 127)
            dz (int): Wheel movement (-127 to 127)
        """
        # Swap buttons if configured
        if self.swap_buttons:
            if buttons & 1:
                buttons = (buttons & ~1) | 2
            elif buttons & 2:
                buttons = (buttons & ~2) | 1

        state = [buttons, dx, dy, dz]
        try:
            self.iface.send_mouse(0, bytes(state))
        except OSError as err:
            print(f"Error sending mouse input: {err}")


# Global client instance
_client = None

def move(dx, dy):
    """Move mouse cursor by relative amounts.

    Args:
        dx (int): X movement
        dy (int): Y movement
    """
    global _client
    if _client is None:
        _client = MouseClient()
    _client.send_mouse(0, dx, dy, 0)

def click(button=1):
    """Click a mouse button.

    Args:
        button (int): Button number (1=left, 2=right, 4=middle)
    """
    global _client
    if _client is None:
        _client = MouseClient()
    _client.send_mouse(button, 0, 0, 0)
    _client.send_mouse(0, 0, 0, 0)  # Release

def scroll(dz):
    """Scroll the mouse wheel.

    Args:
        dz (int): Scroll amount
    """
    global _client
    if _client is None:
        _client = MouseClient()
    _client.send_mouse(0, 0, 0, dz)