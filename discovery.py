"""IPv4 LAN discovery shared by the GUI and headless receivers."""

import ipaddress
import select
import socket
import struct
import threading
import time

import psutil

DISCOVERY_PORT = 5005
QUERY = b"HW?\x01"
ANNOUNCEMENT = struct.Struct("!4sH2x")
MAGIC = b"HWH\x01"
BEACON_INTERVAL = 1.0


def broadcast_targets() -> set[str]:
    """Use every active IPv4 LAN, including hosts with Ethernet and Wi-Fi."""
    targets = set()
    stats = psutil.net_if_stats()
    for name, addresses in psutil.net_if_addrs().items():
        if name not in stats or not stats[name].isup:
            continue
        for address in addresses:
            if address.family != socket.AF_INET or not address.netmask:
                continue
            interface = ipaddress.IPv4Interface(f"{address.address}/{address.netmask}")
            if interface.ip.is_loopback or interface.ip.is_unspecified:
                continue
            if interface.network.prefixlen <= 30:
                targets.add(str(interface.network.broadcast_address))
    # Some embedded stacks accept limited broadcasts but discard subnet-directed
    # broadcasts. Include both; directed targets also reach non-default NICs.
    return targets | {"255.255.255.255"}


class HostDiscovery:
    """Advertise a receiver and answer controller probes until closed."""

    def __init__(self, receiver_port: int, *, discovery_port: int = DISCOVERY_PORT):
        if not 1 <= receiver_port <= 65535:
            raise ValueError("receiver port must be between 1 and 65535")
        self.port = discovery_port
        self.payload = ANNOUNCEMENT.pack(MAGIC, receiver_port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # One receiver per host: do not share the discovery port silently.
            self.socket.bind(("0.0.0.0", discovery_port))
            self.socket.setblocking(False)
        except BaseException:
            self.socket.close()
            raise
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="hid-wifi-discovery", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        next_beacon = 0.0
        targets = set()
        next_interfaces = 0.0
        while not self.stop.is_set():
            now = time.monotonic()
            if now >= next_interfaces:
                try:
                    targets = broadcast_targets()
                except (OSError, ValueError):
                    targets = {"255.255.255.255"}
                next_interfaces = now + 5.0
            if now >= next_beacon:
                for target in targets:
                    try:
                        self.socket.sendto(self.payload, (target, self.port))
                    except OSError:
                        # Interfaces can disappear during DHCP or network changes.
                        pass
                next_beacon = now + BEACON_INTERVAL
            if not select.select([self.socket], [], [], 0.1)[0]:
                continue
            # Limit work per iteration so network traffic cannot starve beacons.
            for _ in range(8):
                try:
                    data, address = self.socket.recvfrom(64)
                except (BlockingIOError, ConnectionResetError):
                    break
                if data == QUERY:
                    try:
                        self.socket.sendto(self.payload, address)
                    except OSError:
                        pass

    def close(self) -> None:
        self.stop.set()
        self.thread.join()
        self.socket.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
