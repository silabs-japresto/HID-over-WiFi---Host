"""Receive the Wi-Fi gamepad on a host without a graphical desktop."""

import argparse
import socket
import time

from discovery import DISCOVERY_PORT, HostDiscovery
from hid_backends import NullGamepad, create_gamepad
from protocol import A, B, decode

TIMEOUT_S = 0.25


def describe(buttons: int) -> str:
    return f"A={'down' if buttons & A else 'up'} B={'down' if buttons & B else 'up'}"


def run(port: int, duration: float, monitor_only: bool) -> int:
    if monitor_only:
        gamepad = NullGamepad()
        print("Monitoring packets without a virtual gamepad", flush=True)
    else:
        try:
            gamepad = create_gamepad()
        except Exception as exc:
            print(f"Cannot create virtual gamepad: {exc}", flush=True)
            return 2

        print("Virtual gamepad active", flush=True)

    start = time.monotonic()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("0.0.0.0", port))
            sock.settimeout(0.05)
            print(f"Listening for UDP gamepad packets on port {port}", flush=True)

            with HostDiscovery(port):
                print(f"Advertising receiver on UDP {DISCOVERY_PORT}", flush=True)
                receive_loop(sock, gamepad, duration, start)
    except OSError as exc:
        print(f"Cannot run receiver: {exc}", flush=True)
        return 1
    except KeyboardInterrupt:
        pass
    finally:
        gamepad.set_buttons(0)
        gamepad.close()

    return 0


def receive_loop(sock, gamepad, duration: float, start: float) -> None:
    peer = None
    sequence = None
    last_packet = 0.0
    buttons = 0
    count = 0

    try:
        while duration <= 0 or time.monotonic() - start < duration:
            if peer is not None and time.monotonic() - last_packet >= TIMEOUT_S:
                if buttons:
                    gamepad.set_buttons(0)
                    buttons = 0
                    print(f"{describe(buttons)} (signal timeout)", flush=True)

                peer = None
                sequence = None

            try:
                data, address = sock.recvfrom(64)
            except socket.timeout:
                data = None

            if data is not None:
                try:
                    packet = decode(data)
                except ValueError:
                    continue

                now = time.monotonic()

                if peer is not None and address != peer and now - last_packet < TIMEOUT_S:
                    continue

                if address != peer or now - last_packet >= TIMEOUT_S:
                    sequence = None
                    peer = address
                    print(f"Source {address[0]}:{address[1]}", flush=True)
                elif sequence is not None:
                    delta = (packet.sequence - sequence) & 255

                    if delta == 0 or delta > 127:
                        continue

                sequence = packet.sequence
                last_packet = now
                count += 1

                if packet.buttons != buttons:
                    gamepad.set_buttons(packet.buttons)
                    buttons = packet.buttons
                    print(f"{describe(buttons)} ({count} packets)", flush=True)
    finally:
        print(f"Received {count} valid packets", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5004)
    parser.add_argument(
        "--duration",
        type=float,
        default=0,
        help="stop after this many seconds (default: run until Ctrl-C)",
    )
    parser.add_argument(
        "--monitor-only",
        action="store_true",
        help="print A/B state without creating a virtual gamepad",
    )
    args = parser.parse_args()

    return run(args.port, args.duration, args.monitor_only)


if __name__ == "__main__":
    raise SystemExit(main())
