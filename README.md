# Si917 Wi-Fi Gamepad Host

> **Example only:** This code is an example and is not intended for production devices. Review and address security considerations before adapting it for production use.

Receives BTN0/A and BTN1/B from the SiWG917 over UDP port 5004 and displays their state in a PySide6 window. On Windows, it creates an Xbox-compatible virtual gamepad through vgamepad. On Linux, it creates a uinput gamepad with A/B buttons and centered, unused axes so gamepad applications can discover it. On macOS, it attempts to create an `IOHIDUserDevice` gamepad. macOS requires an Apple-granted virtual HID entitlement, so an ordinary Python interpreter will usually show an unavailable device status even while UDP monitoring works.

Use Python 3.10 or newer and a Bluetooth adapter for provisioning. The receiving computer and board must be on the same reachable LAN. The GUI shows packet and button state even if virtual gamepad creation fails; check its **Device** line to confirm that OS gamepad output is active.

## Provision Wi-Fi over BLE

Flash the firmware, turn on Bluetooth on this computer, and run:

```sh
python provision.py --ssid YOUR_WIFI_NAME
```

The command scans for `HID-WIFI-917`, prompts for the WPA2 password without echoing it, and waits for the board to join Wi-Fi. Windows and Linux initiate encrypted BLE pairing during connection; macOS pairs when the password characteristic is written. Accept an OS pairing prompt if one appears. On macOS, grant Bluetooth access to the terminal or Python app when prompted. Settings are stored in the 917's NVM and reused after reset. Run the command again to change networks. The board advertises for setup even while Wi-Fi is connected.

## Install and run on Windows

In PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe provision.py --ssid YOUR_WIFI_NAME
.\.venv\Scripts\python.exe app.py --port 5004
```

The `vgamepad` install may ask to install the ViGEmBus driver with administrator approval. Accept and finish that installer before starting `app.py`. If the GUI reports a virtual gamepad error, verify that ViGEmBus is installed and restart the app. Allow incoming UDP port 5004 in Windows Defender Firewall when prompted.

## Install and run on Linux

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python provision.py --ssid YOUR_WIFI_NAME
python app.py --port 5004
```

Linux needs BlueZ running for BLE setup and the `uinput` kernel module loaded for gamepad output. The user running the app needs write access to `/dev/uinput`; if the GUI reports a permission error, check `ls -l /dev/uinput` and configure your distribution's udev permissions. Verify the device and button events with `evtest` or a gamepad tester. Allow incoming UDP port 5004 in your firewall.

### Headless Linux receiver

On a machine without a desktop, install the smaller dependency set and run the terminal receiver:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-headless.txt
python headless.py --port 5004
```

It prints A/B state changes and creates the same uinput gamepad as the GUI. Use `--monitor-only` to inspect UDP packets without uinput access, or `--duration 30` to stop after 30 seconds. A live virtual gamepad still requires write access to `/dev/uinput`.

For initial BLE setup on a headless Linux host, register a BlueZ agent before running `provision.py`. Replace `DEVICE_ADDRESS` with the address shown for `HID-WIFI-917` during the scan:

```text
bluetoothctl --agent NoInputNoOutput
[bluetooth]# default-agent
[bluetooth]# scan on
[bluetooth]# pair DEVICE_ADDRESS
[bluetooth]# disconnect DEVICE_ADDRESS
[bluetooth]# quit
```

Then run `python provision.py --ssid YOUR_WIFI_NAME`. Keep the agent open until pairing reports success. Disconnecting after pairing lets the setup tool scan for the board again. If the board has been paired to another host, remove its old bond from that host's Bluetooth settings before pairing it to a new one.

## Install and run on macOS

Use the Linux Python commands above for the virtual environment and app. On macOS, signing a virtual HID helper requires the restricted `com.apple.developer.hid.virtual.device` entitlement, so the GUI can receive packets while its Device line reports virtual HID unavailable.

On every OS, set the host computer's LAN IPv4 address in the firmware's `hid_wifi_local.h` and rebuild/flash if that address changes. The current firmware cannot discover a moved host automatically.

## Datagram

Exactly six bytes: ASCII `HW`, protocol version `1`, wrapping sequence number, button bitmask (`bit 0 = A`, `bit 1 = B`), and reserved zero. The board sends on change and every 50 ms. The host releases both buttons if no valid packet arrives for 250 ms. Only one source is accepted at a time. Packets are unauthenticated, so use a trusted local network.

To exercise the GUI without hardware:

```sh
python -c 'import socket; from protocol import encode; socket.socket(socket.AF_INET,socket.SOCK_DGRAM).sendto(encode(1,3),("127.0.0.1",5004))'
```

The test packet briefly lights both buttons; the timeout releases them.
