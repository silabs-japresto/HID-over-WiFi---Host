"""Six-byte Si917 button state datagram."""

from dataclasses import dataclass

MAGIC = b"HW"
VERSION = 1
SIZE = 6
A = 1
B = 2


@dataclass(frozen=True)
class Packet:
    sequence: int
    buttons: int


def decode(data: bytes) -> Packet:
    if len(data) != SIZE or data[:2] != MAGIC or data[2] != VERSION or data[5] != 0:
        raise ValueError("invalid HID Wi-Fi datagram")

    if data[4] & ~3:
        raise ValueError("unknown button bits")

    return Packet(data[3], data[4])


def encode(sequence: int, buttons: int) -> bytes:
    if not 0 <= sequence <= 255 or buttons & ~3:
        raise ValueError("invalid packet fields")

    return MAGIC + bytes((VERSION, sequence, buttons, 0))
