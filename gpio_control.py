#!/usr/bin/python3
"""
GPIO button + ACT LED control for jetsoncontrol simulation.

Button: GPIO 17 (pin 11) to GND (pin 9), internal pull-up, active low.
LED:    Built-in ACT (green) via sysfs.

Short press: toggle mouse simulation service (jetsoncontrol-sim).
Long press (5s+): shutdown Jetson.
The HID server (jetsoncontrol) stays running independently.

LED states:
  - Quick blink  = simulation active
  - Off          = simulation stopped
  - Solid ON     = shutdown in progress (hold 5s)
"""

import Jetson.GPIO as GPIO
import subprocess
import time
import signal
import sys

BUTTON_PIN = 17
DEBOUNCE_MS = 300
POLL_INTERVAL = 0.05  # 50ms button poll
LONG_PRESS_SEC = 5.0  # hold for shutdown
LED_PATH = "/sys/class/leds/mmc0"
LED_BLINK_INTERVAL = 0.2  # seconds per blink cycle (quick blink)

SIM_SERVICE = "jetsoncontrol-sim"


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


def is_sim_running():
    return subprocess.run(
        ["systemctl", "is-active", "--quiet", SIM_SERVICE],
        capture_output=True
    ).returncode == 0


def toggle_sim():
    if is_sim_running():
        subprocess.run(["systemctl", "stop", SIM_SERVICE])
    else:
        subprocess.run(["systemctl", "start", SIM_SERVICE])


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
                    press_start = time.monotonic()
                    led_set(True)  # solid ON while holding
                    # Wait for release or long press
                    while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                        held = time.monotonic() - press_start
                        if held >= LONG_PRESS_SEC:
                            print("Long press — graceful shutdown")
                            subprocess.run(["systemctl", "stop", SIM_SERVICE])
                            subprocess.run(["systemctl", "stop", "jetsoncontrol"])
                            led_restore()
                            GPIO.cleanup()
                            subprocess.run(["shutdown", "-h", "now"])
                            sys.exit(0)
                        time.sleep(POLL_INTERVAL)
                    last_press_time = time.monotonic()
                    # Short press — toggle simulation
                    toggle_sim()

            # --- LED handling ---
            if is_sim_running():
                # Slow blink — simulation active
                now = time.monotonic()
                if now - blink_timer > LED_BLINK_INTERVAL / 2:
                    blink_timer = now
                    blink_state = not blink_state
                    led_set(blink_state)
            else:
                led_set(False)

            time.sleep(POLL_INTERVAL)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
