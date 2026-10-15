"""Provision the SiWG917 gamepad over BLE, then let it join Wi-Fi."""

import argparse
import asyncio
import getpass
import sys

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

DEVICE_NAME = "HID-WIFI-917"
COMMAND_UUID = "00001aa1-0000-1000-8000-00805f9b34fb"
STATUS_UUID = "00001bb1-0000-1000-8000-00805f9b34fb"
STATUS = {
    0: "waiting for credentials",
    1: "connecting to Wi-Fi",
    2: "connected to Wi-Fi",
    3: "Wi-Fi connection failed",
    4: "invalid provisioning command",
}


async def send_chunks(client: BleakClient, command: int, value: bytes) -> None:
    for offset in range(0, len(value), 18):
        payload = bytes((command, offset)) + value[offset : offset + 18]
        await client.write_gatt_char(COMMAND_UUID, payload, response=True)


async def provision(ssid: str, password: str, scan_seconds: float) -> int:
    ssid_bytes = ssid.encode("utf-8")
    password_bytes = password.encode("utf-8")
    if not 1 <= len(ssid_bytes) <= 32:
        raise ValueError("SSID must be 1 to 32 UTF-8 bytes")

    if not 8 <= len(password_bytes) <= 63:
        raise ValueError("WPA2 password must be 8 to 63 UTF-8 bytes")

    print(f"Looking for {DEVICE_NAME} over BLE…")

    device = await BleakScanner.find_device_by_filter(
        lambda candidate, data: candidate.name == DEVICE_NAME
        or data.local_name == DEVICE_NAME,
        timeout=scan_seconds,
    )

    if device is None:
        print("Board not found. Check that the new firmware is running and Bluetooth is enabled.")
        return 1

    # CoreBluetooth pairs when the encrypted characteristic is written. BlueZ
    # and WinRT can pair before service discovery, which is more reliable for
    # the board's encrypted command characteristic.
    async with BleakClient(device, timeout=60, pair=sys.platform != "darwin") as client:
        print("Connected to board. Sending Wi-Fi settings…")
        await send_chunks(client, 1, ssid_bytes)
        await send_chunks(client, 2, password_bytes)
        await client.write_gatt_char(COMMAND_UUID, b"\x03", response=True)

        for _ in range(40):
            state = (await client.read_gatt_char(STATUS_UUID))[0]

            if state == 2:
                print(
                    "Board connected to Wi-Fi. "
                    "Start app.py or headless.py to receive A/B inputs."
                )
                return 0

            if state in (3, 4):
                print(f"Board reported: {STATUS[state]}")
                return 1

            await asyncio.sleep(1)

        print("Timed out waiting for Wi-Fi. The board may still be trying to join.")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssid", help="Wi-Fi network name (prompted if omitted)")
    parser.add_argument("--scan-seconds", type=float, default=12)
    args = parser.parse_args()

    ssid = args.ssid or input("Wi-Fi SSID: ")
    password = getpass.getpass("Wi-Fi password: ")

    try:
        return asyncio.run(provision(ssid, password, args.scan_seconds))
    except (BleakError, OSError, TimeoutError, ValueError) as exc:
        detail = str(exc) or type(exc).__name__
        print(f"Provisioning failed: {detail}", file=sys.stderr)

        if sys.platform == "linux" and "AuthenticationFailed" in detail:
            print(
                "On a headless Linux host, pair once with a BlueZ NoInputNoOutput "
                "agent as shown in README.md.",
                file=sys.stderr,
            )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
