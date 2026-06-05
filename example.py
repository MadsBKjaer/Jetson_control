#!/usr/bin/env python3
"""
Example usage of jetson-control package for AI models.

This script demonstrates how to use the jetson-control package
to send keyboard and mouse inputs via Bluetooth HID and capture
screenshots from the host computer.
"""

from jetson_control.keyboard import send_string, send_key
from jetson_control.mouse import move, click, scroll
from jetson_control.screen import capture_screenshot, capture_region
import time

def main():
    print("Testing jetson-control package...")

    # Wait a bit for connections
    time.sleep(2)

    # Send some keyboard input
    print("Sending keyboard input...")
    send_string("Hello from AI model!")
    time.sleep(1)

    # Send some mouse input
    print("Sending mouse input...")
    move(50, 0)  # Move right
    time.sleep(0.5)
    move(0, 50)  # Move down
    time.sleep(0.5)
    click(1)     # Left click
    time.sleep(0.5)
    scroll(3)    # Scroll up
    time.sleep(1)

    # Capture screenshot
    print("Capturing screenshot...")
    screenshot = capture_screenshot()
    if screenshot:
        screenshot.save("screenshot.png")
        print("Screenshot saved as screenshot.png")
    else:
        print("Failed to capture screenshot")

    # Capture region
    print("Capturing screen region...")
    region = capture_region(100, 100, 400, 300)
    if region:
        region.save("region.png")
        print("Region saved as region.png")
    else:
        print("Failed to capture region")

    print("Test complete!")

if __name__ == "__main__":
    main()