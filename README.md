# Jetson Orin Nano Bluetooth Keyboard & Mouse Emulator

Turn your Jetson Orin Nano into a Bluetooth keyboard and mouse for Windows 10/11, macOS, Linux, Android, and iPad.

Adapted from [thanhlev/keyboard_mouse_emulate_on_raspberry](https://github.com/thanhlev/keyboard_mouse_emulate_on_raspberry) with added Windows 10/11 support.

## What's different from the original

- Auto-pairing without PIN code (SSP "Just Works" agent)
- Windows 10/11 compatibility (audio profile rejection, correct device class)
- No `pybluez` dependency (uses raw `socket.BTPROTO_L2CAP`)
- Single process handles both pairing and HID serving
- Can run as a systemd service (auto-start on boot)
- Human-like mouse simulation (movements, clicks, scrolling)
- GPIO button to toggle simulation + ACT LED status indicator

## Setup

### Step 1: Install dependencies

```
sudo ./setup.sh
```

This installs BlueZ, Python packages, configures D-BUS permissions, and disables Bluetooth audio plugins (required for Windows compatibility).

### Step 2: Configure (optional)

Edit `config.ini`:

```ini
[device]
name = JetsonControl

[mouse]
# Set to true if Windows has "swap mouse buttons" enabled
swap_buttons = false

[simulation]
# Mouse movement area (pixels), centered at initial cursor position
area_width = 600
area_height = 300
```

### Step 3: Start the server

**Option A — Run manually:**
```
sudo python3 server/btk_server.py
```

**Option B — Install as systemd services (auto-start on boot):**
```
sudo ./install_service.sh
```

This installs three services:
- `jetsoncontrol` — Bluetooth HID server (pairing + input)
- `jetsoncontrol-sim` — mouse simulation (auto-starts with server)
- `jetsoncontrol-gpio` — GPIO button + LED control

### Step 4: Pair a host device (one-time)

On your host: **Settings → Bluetooth & devices → Add device** → find the device name → click to pair.

The device will pair automatically without a PIN.

### Step 5: Send input (after pairing)

**Keyboard (physical):**
```
./keyboard/kb_client.py
```

**Keyboard (send string programmatically):**
```
./keyboard/send_string.py "hello world"
```

**Mouse (physical USB mouse forwarded via Bluetooth):**
```
./mouse/mouse_client.py
```

**Mouse (programmatic):**
```
./mouse/mouse_emulate.py 0 10 0 0
```
Arguments: `[button_bitmask] [dx] [dy] [dz]`

## Mouse simulation

`mouse/mouse_simulate.py` generates human-like mouse activity to keep the host machine active. It simulates reading a web page:

1. **Reading phase** — scrolls down, moves cursor, clicks (15–40 actions with natural pauses)
2. **Return to top** — fast scroll up (simulating going back to the top of the page)
3. **Repeat**

Movement is constrained to a configurable rectangle (`area_width` × `area_height` in `config.ini`), centered at the screen center. Near edges, the cursor slows down and steers back toward the center.

Statistics are logged every minute:
```
[3m00s] moves=42 clicks=18 scrolls=12 pos=(985,527)
```

## GPIO button + LED

Connect a momentary button between **GPIO 17** (pin 11) and **GND** (pin 9).

- **Press button** → toggle mouse simulation on/off
- **LED quick blink** → simulation is running
- **LED off** → simulation is stopped

The HID server runs independently and is not affected by the button.

## Re-pairing

If pairing fails or you need to pair a different device:

1. Remove old pairing from Jetson:
   ```
   sudo ./unpair.sh
   ```
2. Remove the device from your host (Windows: Bluetooth settings → Remove device)
3. If running as a service, restart it: `sudo systemctl restart jetsoncontrol`
4. Pair again from your host (the server is always ready for new pairings)

## Service management

After installing with `install_service.sh`:

```
sudo systemctl status jetsoncontrol         # HID server status
sudo systemctl status jetsoncontrol-sim     # mouse simulation status
sudo systemctl status jetsoncontrol-gpio    # GPIO control status
sudo journalctl -u jetsoncontrol -f         # server logs
sudo journalctl -u jetsoncontrol-sim -f     # simulation logs
```

## Uninstall

```
sudo ./uninstall.sh
```

This removes all three systemd services, restores the ACT LED, removes D-BUS config, Bluetooth noplugin settings, and all pairings. Installed packages are kept — remove manually if needed.

## Bluetooth service configuration

`setup.sh` configures bluetoothd via a systemd drop-in (`/etc/systemd/system/bluetooth.service.d/jetsonbt.conf`):
```
--compat --noplugin=sap,input,audio,a2dp,avrcp,network,hfp,hsp
```

This prevents Windows from detecting the Jetson as a microphone/audio device. To restore default Bluetooth behavior, run `uninstall.sh`.

## Background reading

- [Make Raspberry Pi3 as an emulator bluetooth keyboard](https://thanhle.me/make-raspberry-pi3-as-an-emulator-bluetooth-keyboard/)
- [Emulate Bluetooth mouse with Raspberry Pi](https://thanhle.me/emulate-bluetooth-mouse-with-raspberry-pi/)
