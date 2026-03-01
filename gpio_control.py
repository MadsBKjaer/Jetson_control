#!/usr/bin/python3
"""
GPIO button (start/stop) + ACT LED status for raspicontrol.

Button: GPIO 17 (pin 11) to GND (pin 9), internal pull-up, active low.
LED:    Built-in ACT (green) via sysfs.

States:
  - LED solid ON  = server running + HID connected
  - LED slow blink = server running, waiting for connection
  - LED off       = server stopped
"""

import RPi.GPIO as GPIO
import subprocess
import time
import signal
import sys

BUTTON_PIN = 17
DEBOUNCE_MS = 300
POLL_INTERVAL = 0.05  # 50ms button poll
LED_PATH = "/sys/class/leds/ACT"
LED_BLINK_INTERVAL = 1.0  # seconds per blink cycle


def led_init():
    """Take over ACT LED by setting trigger to none."""
    with open(LED_PATH + "/trigger", "w") as f:
        f.write("none")
    led_set(False)


def led_restore():
    """Restore ACT LED to default mmc0 trigger."""
    try:
        with open(LED_PATH + "/trigger", "w") as f:
            f.write("mmc0")
    except OSError:
        pass


def led_set(on):
    try:
        with open(LED_PATH + "/brightness", "w") as f:
            f.write("1" if on else "0")
    except OSError:
        pass


def is_server_running():
    return subprocess.run(
        ["systemctl", "is-active", "--quiet", "raspicontrol"],
        capture_output=True
    ).returncode == 0


def is_hid_connected():
    result = subprocess.run(["hcitool", "con"], capture_output=True, text=True)
    return "ACL" in result.stdout


def toggle_server():
    if is_server_running():
        subprocess.run(["systemctl", "stop", "raspicontrol"])
    else:
        subprocess.run(["systemctl", "start", "raspicontrol"])


def cleanup(_sig=None, _frame=None):
    led_restore()
    GPIO.cleanup()
    sys.exit(0)


def main():
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    led_init()

    last_press_time = 0
    blink_state = False
    blink_timer = 0

    try:
        while True:
            # --- Button handling ---
            if GPIO.input(BUTTON_PIN) == GPIO.LOW:
                now = time.monotonic()
                if now - last_press_time > DEBOUNCE_MS / 1000:
                    last_press_time = now
                    toggle_server()
                    # Wait for button release
                    while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                        time.sleep(POLL_INTERVAL)

            # --- LED handling ---
            server_up = is_server_running()
            if not server_up:
                led_set(False)
            elif is_hid_connected():
                led_set(True)
            else:
                # Slow blink — toggle every LED_BLINK_INTERVAL/2
                now = time.monotonic()
                if now - blink_timer > LED_BLINK_INTERVAL / 2:
                    blink_timer = now
                    blink_state = not blink_state
                    led_set(blink_state)

            time.sleep(POLL_INTERVAL)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
