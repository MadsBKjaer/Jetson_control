# Raspberry Pi Bluetooth Keyboard & Mouse Emulator

Turn your Raspberry Pi into a Bluetooth keyboard and mouse for Windows 10/11, macOS, Linux, Android, and iPad.

Forked from [thanhlev/keyboard_mouse_emulate_on_raspberry](https://github.com/thanhlev/keyboard_mouse_emulate_on_raspberry) with added Windows 10/11 support.

## What's different from the original

- Auto-pairing without PIN code (SSP "Just Works" agent)
- Windows 10/11 compatibility (audio profile rejection, correct device class)
- No `pybluez` dependency (uses raw `socket.BTPROTO_L2CAP`)
- Single process handles both pairing and HID serving
- Can run as a systemd service (auto-start on boot)

## Setup

### Step 1: Install dependencies

```
sudo ./setup.sh
```

This installs BlueZ, Python packages, configures D-BUS permissions, and disables Bluetooth audio plugins (required for Windows compatibility).

### Step 2: Configure (optional)

Edit `config.ini` to change the device name visible during Bluetooth discovery:

```ini
[device]
name = RaspiControl
```

### Step 3: Start the server

**Option A — Run manually:**
```
sudo python3 server/btk_server.py
```

**Option B — Install as a systemd service (auto-start on boot):**
```
sudo ./install_service.sh
```

The server handles both pairing and HID serving. On first run (no paired devices), it waits for a host to pair. On subsequent runs, paired hosts reconnect automatically.

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

## Re-pairing

If pairing fails or you need to pair a different device:

1. Remove old pairing from RPi:
   ```
   sudo ./unpair.sh
   ```
2. Remove the device from your host (Windows: Bluetooth settings → Remove device)
3. If running as a service, restart it: `sudo systemctl restart raspicontrol`
4. Pair again from your host (the server is always ready for new pairings)

## Service management

After installing with `install_service.sh`:

```
sudo systemctl status raspicontrol     # check status
sudo journalctl -u raspicontrol -f     # view logs
sudo systemctl stop raspicontrol       # stop
sudo systemctl start raspicontrol      # start
sudo systemctl restart raspicontrol    # restart
```

## Uninstall

```
sudo ./uninstall.sh
```

This removes the systemd service, D-BUS config, Bluetooth noplugin settings, and all pairings. Installed packages are kept — remove manually if needed.

## Bluetooth service configuration

`setup.sh` configures bluetoothd via a systemd drop-in (`/etc/systemd/system/bluetooth.service.d/raspibt.conf`):
```
--compat --noplugin=sap,input,a2dp,avrcp,network,hfp,hsp
```

This prevents Windows from detecting the Raspberry Pi as a microphone/audio device. To restore default Bluetooth behavior, run `uninstall.sh`.

## Background reading

- [Make Raspberry Pi3 as an emulator bluetooth keyboard](https://thanhle.me/make-raspberry-pi3-as-an-emulator-bluetooth-keyboard/)
- [Emulate Bluetooth mouse with Raspberry Pi](https://thanhle.me/emulate-bluetooth-mouse-with-raspberry-pi/)
