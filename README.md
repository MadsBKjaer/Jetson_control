# Raspberry Pi Bluetooth Keyboard & Mouse Emulator

Turn your Raspberry Pi into a Bluetooth keyboard and mouse for Windows 10/11, macOS, Linux, Android, and iPad.

Forked from [thanhlev/keyboard_mouse_emulate_on_raspberry](https://github.com/thanhlev/keyboard_mouse_emulate_on_raspberry) with added Windows 10/11 support.

## What's different from the original

- Auto-pairing without PIN code (SSP "Just Works" agent)
- Windows 10/11 compatibility (audio profile rejection, correct device class)
- No `pybluez` dependency (uses raw `socket.BTPROTO_L2CAP`)
- Single process handles pairing + HID server simultaneously

## Setup

### Step 1: Install dependencies

```
sudo ./setup.sh
```

This installs BlueZ, Python packages, configures D-BUS permissions, and disables Bluetooth audio plugins (required for Windows compatibility).

### Step 2: Configure target host MAC address

Edit `server/btk_server.py` and set `TARGET_ADDRESS` to your host PC's Bluetooth MAC address.

**How to find the MAC on Windows:**
```cmd
ipconfig /all
```
Look for "Bluetooth Network Connection" → "Physical Address" (e.g. `40-EC-99-50-CF-E3`), replace dashes with colons: `40:EC:99:50:CF:E3`.

### Step 3: Start the server

```
sudo python3 server/btk_server.py
```

The server will:
1. Register as a Bluetooth HID device (keyboard + mouse)
2. Set up auto-pairing agent (no PIN required)
3. Make the device discoverable
4. Wait for a host to connect

### Step 4: Pair from your host

On Windows: **Settings → Bluetooth & devices → Add device** → find "ThanhLe_Keyboard_Mouse" → click to pair.

The device will pair automatically and connect as a keyboard.

### Step 5: Send input

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

## Bluetooth service configuration

`setup.sh` configures bluetoothd with:
```
--noplugin=input,audio,a2dp,avrcp,sap
```

This prevents Windows from detecting the Raspberry Pi as a microphone/audio device. If you need to restore default Bluetooth behavior, remove the `--noplugin` flag from `/lib/systemd/system/bluetooth.service`.

## Background reading

- [Make Raspberry Pi3 as an emulator bluetooth keyboard](https://thanhle.me/make-raspberry-pi3-as-an-emulator-bluetooth-keyboard/)
- [Emulate Bluetooth mouse with Raspberry Pi](https://thanhle.me/emulate-bluetooth-mouse-with-raspberry-pi/)
