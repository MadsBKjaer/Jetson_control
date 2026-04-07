#!/usr/bin/python3
"""
Human-like mouse activity simulator.

Connects to the HID server via D-Bus and generates realistic mouse
movements, clicks, and scrolling to keep a Windows machine active.
Designed to run for hours with varied, non-repetitive patterns.

Mouse stays within a configurable rectangle (set in config.ini),
centered at the initial cursor position. Near edges, movement slows
and steers back toward center.
"""

import configparser
import dbus
import dbus.mainloop.glib
import time
import random
import math
import signal
import sys
import os
from datetime import datetime
import json

# Screen hard bounds
SCREEN_W = 1920
SCREEN_H = 1080

# Movement step delay
STEP_DELAY = 0.015  # 15ms between incremental moves

# D-Bus retry
DBUS_RETRY_INTERVAL = 5

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.ini")
config = configparser.ConfigParser()
config.read(CONFIG_PATH)

AREA_W = config.getint("simulation", "area_width", fallback=600)
AREA_H = config.getint("simulation", "area_height", fallback=300)
SWAP_BUTTONS = config.getboolean("mouse", "swap_buttons", fallback=False)
LEFT_BUTTON = 2 if SWAP_BUTTONS else 1

STATS_FILE = "/var/tmp/jetsoncontrol-sim-stats.json"


class MouseSim:
    def __init__(self):
        # Initial position = screen center
        self.x = SCREEN_W // 2
        self.y = SCREEN_H // 2

        # Rectangle bounds centered at initial position, clamped to screen
        self.rect_left = max(0, self.x - AREA_W // 2)
        self.rect_right = min(SCREEN_W, self.x + AREA_W // 2)
        self.rect_top = max(0, self.y - AREA_H // 2)
        self.rect_bottom = min(SCREEN_H, self.y + AREA_H // 2)

        # Center of rectangle (for bias calculations)
        self.cx = (self.rect_left + self.rect_right) // 2
        self.cy = (self.rect_top + self.rect_bottom) // 2

        self.bus = None
        self.iface = None
        self.running = True

        # Stats — load accumulated daily stats from file
        self.stats_session_start = time.monotonic()
        self.stats_last_log = self.stats_session_start
        self.stats_today = str(datetime.now().date())
        self._load_daily_stats()

    def connect_dbus(self):
        """Connect to HID server D-Bus, retrying until successful."""
        while self.running:
            try:
                self.bus = dbus.SystemBus()
                service = self.bus.get_object(
                    'wof2.jetsoncontrol.service',
                    '/wof2/jetsoncontrol/service')
                self.iface = dbus.Interface(service, 'wof2.jetsoncontrol.service')
                print("Connected to HID server via D-Bus")
                return
            except dbus.exceptions.DBusException as e:
                print("D-Bus not ready: %s — retrying in %ds" % (e, DBUS_RETRY_INTERVAL))
                time.sleep(DBUS_RETRY_INTERVAL)

    def send_mouse(self, buttons, dx, dy, dz):
        """Send a single mouse HID report."""
        state = [
            buttons & 0xFF,
            dx & 0xFF,
            dy & 0xFF,
            dz & 0xFF,
        ]
        try:
            self.iface.send_mouse(0, bytes(state))
        except dbus.exceptions.DBusException:
            print("D-Bus send failed, reconnecting...")
            self.connect_dbus()

    def _edge_ratio(self):
        """How close to the rectangle edge (0=center, 1=at edge)."""
        half_w = (self.rect_right - self.rect_left) / 2
        half_h = (self.rect_bottom - self.rect_top) / 2
        if half_w == 0 or half_h == 0:
            return 0
        rx = abs(self.x - self.cx) / half_w
        ry = abs(self.y - self.cy) / half_h
        return max(rx, ry)

    def _clamp(self, x, y):
        """Clamp position to rectangle AND screen bounds."""
        x = max(self.rect_left, min(self.rect_right, x))
        y = max(self.rect_top, min(self.rect_bottom, y))
        x = max(0, min(SCREEN_W, x))
        y = max(0, min(SCREEN_H, y))
        return x, y

    def move_to(self, tx, ty):
        """Move cursor to target position with natural multi-step motion."""
        tx, ty = self._clamp(tx, ty)

        dx_total = tx - self.x
        dy_total = ty - self.y
        dist = math.hypot(dx_total, dy_total)
        if dist < 1:
            return

        # Fewer steps near edges = slower movement
        edge = self._edge_ratio()
        if edge > 0.85:
            steps = max(8, int(dist / random.uniform(2, 4)))
        else:
            steps = max(5, int(dist / random.uniform(3, 8)))

        for i in range(steps):
            t = (i + 1) / steps
            ease = t * t * (3 - 2 * t)  # smoothstep

            target_x = self.x + dx_total * ease
            target_y = self.y + dy_total * ease

            if i == 0:
                prev_x, prev_y = float(self.x), float(self.y)
            else:
                t_prev = i / steps
                ease_prev = t_prev * t_prev * (3 - 2 * t_prev)
                prev_x = self.x + dx_total * ease_prev
                prev_y = self.y + dy_total * ease_prev

            step_dx = target_x - prev_x
            step_dy = target_y - prev_y

            jitter = random.gauss(0, 0.5)
            sdx = int(round(step_dx + jitter))
            sdy = int(round(step_dy + jitter))

            sdx = max(-127, min(127, sdx))
            sdy = max(-127, min(127, sdy))

            if sdx != 0 or sdy != 0:
                self.send_mouse(0, sdx, sdy, 0)
                delay = STEP_DELAY + random.uniform(-0.005, 0.005)
                if edge > 0.85:
                    delay *= 1.5  # slower near edge
                time.sleep(delay)

        self.x = tx
        self.y = ty
        self.stats_moves += 1

    def click(self):
        """Perform a left click."""
        self.send_mouse(LEFT_BUTTON, 0, 0, 0)   # left button down
        time.sleep(random.uniform(0.05, 0.12))
        self.send_mouse(0, 0, 0, 0)   # release
        self.stats_clicks += 1

    def scroll(self, ticks, direction=-1):
        """Scroll with natural per-tick delays. direction: -1=down, 1=up."""
        for _ in range(ticks):
            self.send_mouse(0, 0, 0, direction & 0xFF)
            time.sleep(random.uniform(0.1, 0.4))
        self.stats_scrolls += 1

    def _load_daily_stats(self):
        """Load accumulated stats for today from file, or start fresh."""
        try:
            with open(STATS_FILE, "r") as f:
                data = json.load(f)
            if data.get("date") == self.stats_today:
                self.stats_moves = data.get("moves", 0)
                self.stats_clicks = data.get("clicks", 0)
                self.stats_scrolls = data.get("scrolls", 0)
                self.stats_uptime = data.get("uptime", 0)
                print("Resumed daily stats: moves=%d clicks=%d scrolls=%d uptime=%ds" % (
                    self.stats_moves, self.stats_clicks, self.stats_scrolls, self.stats_uptime))
                return
        except (OSError, json.JSONDecodeError, KeyError):
            pass
        self.stats_moves = 0
        self.stats_clicks = 0
        self.stats_scrolls = 0
        self.stats_uptime = 0

    def _save_daily_stats(self):
        """Save accumulated stats to file."""
        session_secs = int(time.monotonic() - self.stats_session_start)
        data = {
            "date": self.stats_today,
            "moves": self.stats_moves,
            "clicks": self.stats_clicks,
            "scrolls": self.stats_scrolls,
            "uptime": self.stats_uptime + session_secs,
        }
        try:
            with open(STATS_FILE, "w") as f:
                json.dump(data, f)
        except OSError:
            pass

    def _total_uptime(self):
        """Total uptime today: previous sessions + current session."""
        return self.stats_uptime + int(time.monotonic() - self.stats_session_start)

    def log_stats(self):
        """Print stats if a minute has passed since last log. Daily summary at midnight."""
        now = time.monotonic()
        today = str(datetime.now().date())

        # Daily summary at midnight
        if today != self.stats_today:
            uptime = self._total_uptime()
            hours = uptime // 3600
            mins = (uptime % 3600) // 60
            print("=== DAILY SUMMARY %s === uptime=%dh%02dm moves=%d clicks=%d scrolls=%d" % (
                self.stats_today, hours, mins,
                self.stats_moves, self.stats_clicks, self.stats_scrolls))
            # Reset for new day
            self.stats_today = today
            self.stats_moves = 0
            self.stats_clicks = 0
            self.stats_scrolls = 0
            self.stats_uptime = 0
            self.stats_session_start = now

        if now - self.stats_last_log >= 60:
            self.stats_last_log = now
            uptime = self._total_uptime()
            mins = uptime // 60
            secs = uptime % 60
            print("[%dm%02ds] moves=%d clicks=%d scrolls=%d pos=(%d,%d)" % (
                mins, secs, self.stats_moves, self.stats_clicks,
                self.stats_scrolls, self.x, self.y))
            self._save_daily_stats()

    def random_target(self):
        """Generate a random target within rectangle, biased toward center near edges."""
        edge = self._edge_ratio()

        if edge > 0.7:
            # Near edge — steer toward center with random deviation
            bias = 0.4 + random.uniform(0, 0.4)  # pull 40-80% toward center
            tx = self.x + (self.cx - self.x) * bias + int(random.gauss(0, 30))
            ty = self.y + (self.cy - self.y) * bias + int(random.gauss(0, 20))
        elif random.random() < 0.15:
            # Occasional larger jump within rectangle
            tx = random.randint(self.rect_left + 20, self.rect_right - 20)
            ty = random.randint(self.rect_top + 20, self.rect_bottom - 20)
        else:
            # Small-medium move near current position
            tx = self.x + int(random.gauss(0, 60))
            ty = self.y + int(random.gauss(0, 40))

        tx, ty = self._clamp(tx, ty)
        return int(tx), int(ty)

    def random_pause(self):
        """Wait a human-like duration between actions."""
        r = random.random()
        if r < 0.60:
            time.sleep(random.uniform(0.5, 3.0))
        elif r < 0.90:
            time.sleep(random.uniform(3.0, 10.0))
        else:
            time.sleep(random.uniform(15.0, 60.0))

    def read_action(self):
        """Single action while 'reading' a page: move, click, or scroll down."""
        r = random.random()

        if r < 0.40:
            tx, ty = self.random_target()
            self.move_to(tx, ty)

        elif r < 0.55:
            tx, ty = self.random_target()
            self.move_to(tx, ty)
            time.sleep(random.uniform(0.1, 0.3))
            self.click()

        else:
            ticks = random.randint(1, 4)
            self.scroll(ticks, direction=-1)

    def scroll_to_top(self):
        """Fast scroll back to top of page."""
        total_ticks = random.randint(15, 40)
        print("Scrolling to top (%d ticks)" % total_ticks)
        remaining = total_ticks
        while remaining > 0 and self.running:
            burst = min(remaining, random.randint(3, 8))
            self.scroll(burst, direction=1)
            remaining -= burst
            if remaining > 0:
                time.sleep(random.uniform(0.1, 0.3))

    def read_page(self):
        """Simulate reading one page: many actions scrolling down, then scroll to top."""
        actions = random.randint(15, 40)
        print("Reading page (%d actions)" % actions)
        for _ in range(actions):
            if not self.running:
                return
            self.read_action()
            self.log_stats()
            self.random_pause()

        # Pause before scrolling back to top
        time.sleep(random.uniform(1.0, 3.0))
        self.scroll_to_top()

    def run(self):
        """Main simulation loop."""
        self.connect_dbus()
        print("Simulation started (pos %d,%d, area %dx%d)" % (
            self.x, self.y, AREA_W, AREA_H))
        print("Rectangle: [%d,%d] - [%d,%d]" % (
            self.rect_left, self.rect_top, self.rect_right, self.rect_bottom))

        while self.running:
            try:
                self.read_page()
                self.log_stats()
                # Pause between "pages"
                time.sleep(random.uniform(2.0, 5.0))
            except Exception as e:
                print("Action error: %s — reconnecting" % e)
                self.connect_dbus()


def main():
    sim = MouseSim()

    def shutdown(_sig=None, _frame=None):
        print("\nSimulation stopping...")
        sim.running = False
        sim._save_daily_stats()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    sim.run()


if __name__ == "__main__":
    main()
