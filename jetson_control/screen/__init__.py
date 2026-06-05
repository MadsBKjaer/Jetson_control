"""
Screen capture module for Jetson Control.

Provides functions to capture screenshots from the host computer via VNC.
"""

import configparser
import os
import time
from io import BytesIO
from PIL import Image
from vncdotool import api


class ScreenCapture:
    """Handles screen capture via VNC connection to the host."""

    def __init__(self):
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.ini")
        config = configparser.ConfigParser()
        config.read(config_path)

        self.vnc_host = config.get("screen", "vnc_host", fallback="192.168.1.100")
        self.vnc_port = config.getint("screen", "vnc_port", fallback=5900)
        self.vnc_password = config.get("screen", "vnc_password", fallback="")

        self.client = None

    def _is_connected(self):
        """Check if the VNC client is connected and has a live protocol."""
        return (
            self.client is not None
            and self.client.protocol is not None
            and self.client.protocol.transport is not None
            and self.client.protocol.transport.connected
        )

    def connect(self):
        """Connect to the VNC server.

        Returns True on success. api.connect() is non-blocking — the TCP
        handshake happens in a Twisted background thread, so we do a quick
        probe capture to verify the connection is truly ready.
        """
        if self._is_connected():
            return True

        # Tear down any stale client first
        self.disconnect()

        try:
            self.client = api.connect(
                f"{self.vnc_host}::{self.vnc_port}",
                password=self.vnc_password or None,
            )
        except Exception as e:
            print(f"[ScreenCapture] Failed to initiate VNC connection: {e}")
            self.client = None
            return False

        # api.connect() is async — wait briefly for the Twisted reactor to
        # complete the handshake before declaring success.
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if self._is_connected():
                return True
            time.sleep(0.1)

        print(
            f"[ScreenCapture] Timeout waiting for VNC handshake with "
            f"{self.vnc_host}:{self.vnc_port}"
        )
        self.disconnect()
        return False

    def disconnect(self):
        """Disconnect from the VNC server."""
        if self.client is not None:
            try:
                self.client.disconnect()
            except Exception:
                pass
        self.client = None

    def capture_screenshot(self):
        """Capture a screenshot and return as PIL Image.

        Returns:
            PIL.Image: Screenshot image, or None if failed
        """
        if not self.connect():
            print(
                f"[ScreenCapture] Cannot capture — not connected to "
                f"{self.vnc_host}:{self.vnc_port}"
            )
            return None

        try:
            buffer = BytesIO()
            self.client.captureScreen(buffer, format="PNG")
            buffer.seek(0)
            image = Image.open(buffer)
            image.load()  # Load image data before buffer is discarded
            return image
        except Exception as e:
            print(f"[ScreenCapture] Failed to capture screenshot: {e}")
            self.disconnect()
            return None

    def capture_region(self, x, y, width, height):
        """Capture a specific region of the screen.

        Args:
            x, y: Top-left coordinates
            width, height: Region size

        Returns:
            PIL.Image: Cropped screenshot, or None if failed
        """
        full_image = self.capture_screenshot()
        if full_image is None:
            return None

        region = full_image.crop((x, y, x + width, y + height))
        return region


# Global client instance
_client = None


def capture_screenshot():
    """Capture a screenshot from the host computer.

    Returns:
        PIL.Image: Screenshot image, or None if failed
    """
    global _client
    if _client is None:
        _client = ScreenCapture()
    return _client.capture_screenshot()


def capture_region(x, y, width, height):
    """Capture a specific region of the host screen.

    Args:
        x, y: Top-left coordinates
        width, height: Region size

    Returns:
        PIL.Image: Cropped screenshot, or None if failed
    """
    global _client
    if _client is None:
        _client = ScreenCapture()
    return _client.capture_region(x, y, width, height)