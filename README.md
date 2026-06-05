# Jetson Orin Nano Bluetooth Keyboard & Mouse Emulator

Turn your Jetson Orin Nano into a Bluetooth keyboard and mouse interface for AI models, compatible with Windows 10/11, macOS, Linux, Android, and iPad.

Adapted from [thanhlev/keyboard_mouse_emulate_on_raspberry](https://github.com/thanhlev/keyboard_mouse_emulate_on_raspberry) with added Windows 10/11 support.

## Installation

### As a Python Package

```bash
pip install -e .
```

This installs the `jetson-control` package for use in your AI model.

### System Setup

1. Run the system setup:
```bash
sudo ./setup.sh
```

2. Install the service:
```bash
sudo ./install_service.sh
```

This installs the service:
- `jetsoncontrol` — Bluetooth HID server (pairing + input)

## Screen Capture Setup

To enable screen capture from the host computer:

1. **Install VNC server on the host:**
   - **Windows**: Install TightVNC, RealVNC, or UltraVNC server
   - **macOS**: System Preferences → Sharing → Screen Sharing (enable VNC)
   - **Linux**: Install TightVNC or x11vnc

2. **Configure VNC settings:**
   Edit `config.ini`:
   ```ini
   [screen]
   vnc_host = 192.168.1.100  # IP address of host computer
   vnc_port = 5900           # VNC port (default 5900)
   vnc_password = your_password  # VNC password (leave empty if none)
   ```

3. **Usage in AI models:**
   ```python
   from jetson_control.screen import capture_screenshot, capture_region

   # Capture full screen
   screenshot = capture_screenshot()
   if screenshot:
       screenshot.save("screen.png")

   # Capture region (x=100, y=100, width=800, height=600)
   region = capture_region(100, 100, 800, 600)
   ```

**Note:** For low latency, use a fast VNC server and ensure the host and Jetson are on the same network. VNC typically provides 50-200ms latency depending on network and settings.

## Manual Usage

**Keyboard (send string programmatically):**
```
./keyboard/send_string.py "hello world"
```

**Mouse (programmatic):**
```
./mouse/mouse_emulate.py 0 10 0 0
```
Arguments: `[button_bitmask] [dx] [dy] [dz]`

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
