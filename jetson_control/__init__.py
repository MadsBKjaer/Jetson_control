"""
Jetson Control - Bluetooth HID Interface for AI Models

This package provides a Bluetooth HID (Human Interface Device) interface
for Jetson devices to act as wireless keyboards and mice for host computers.
It also includes screen capture functionality for visual feedback.

Features:
- Bluetooth keyboard and mouse emulation
- Easy-to-use Python API for sending inputs
- Screen capture via VNC for visual feedback
- Compatible with Windows, macOS, Linux, Android, iPad
- Auto-pairing without PIN codes
- Runs as a systemd service for reliability
"""

__version__ = "1.0.0"
__author__ = "Adapted from thanhlev/keyboard_mouse_emulate_on_raspberry"