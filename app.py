"""UDP receiver and live A/B gamepad monitor."""

import argparse
import socket
import sys
import time

from PySide6.QtCore import QSocketNotifier, QTimer
from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QMainWindow, QWidget

from discovery import DISCOVERY_PORT, HostDiscovery
from hid_backends import NullGamepad, create_gamepad
from protocol import A, B, decode

TIMEOUT_S = 0.25


class Window(QMainWindow):
    def __init__(self, port: int):
        super().__init__()
        self.setWindowTitle("Si917 Wi-Fi Gamepad")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("0.0.0.0", port))
        self.socket.setblocking(False)
        self.notifier = QSocketNotifier(self.socket.fileno(), QSocketNotifier.Type.Read)
        self.notifier.activated.connect(self.receive)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_timeout)
        self.timer.start(25)
        self.peer = None
        self.sequence = None
        self.last_packet = 0.0
        self.buttons = 0
        self.count = 0

        try:
            self.gamepad = create_gamepad()
            backend = "Virtual gamepad active"
        except Exception as exc:
            self.gamepad = NullGamepad()
            backend = f"Virtual gamepad unavailable: {exc}"

        try:
            self.discovery = HostDiscovery(port)
        except OSError:
            self.notifier.setEnabled(False)
            self.socket.close()
            self.gamepad.close()
            raise

        center = QWidget()
        grid = QGridLayout(center)
        self.labels = {}
        for row, (key, value) in enumerate((
            ("Listening", f"UDP 0.0.0.0:{port}"),
            ("Discovery", f"Advertising on UDP {DISCOVERY_PORT}"),
            ("Device", backend),
            ("Source", "Waiting for board"),
            ("A / BTN0", "Released"),
            ("B / BTN1", "Released"),
            ("Packets", "0"),
        )):
            grid.addWidget(QLabel(key), row, 0)
            label = QLabel(value)
            label.setWordWrap(True)
            grid.addWidget(label, row, 1)
            self.labels[key] = label
        self.setCentralWidget(center)
        self.resize(620, 220)

    def receive(self):
        while True:
            try:
                data, address = self.socket.recvfrom(64)
            except BlockingIOError:
                return
            try:
                packet = decode(data)
            except ValueError:
                continue
            now = time.monotonic()
            if self.peer is not None and address != self.peer and now - self.last_packet < TIMEOUT_S:
                continue
            if address != self.peer or now - self.last_packet >= TIMEOUT_S:
                self.sequence = None
                self.peer = address
                self.labels["Source"].setText(f"{address[0]}:{address[1]}")
            elif self.sequence is not None:
                delta = (packet.sequence - self.sequence) & 255
                if delta == 0 or delta > 127:
                    continue
            self.sequence = packet.sequence
            self.last_packet = now
            self.count += 1
            self.labels["Packets"].setText(str(self.count))
            self.apply_buttons(packet.buttons)

    def apply_buttons(self, buttons: int):
        if buttons == self.buttons:
            return
        self.buttons = buttons
        self.labels["A / BTN0"].setText("PRESSED" if buttons & A else "Released")
        self.labels["B / BTN1"].setText("PRESSED" if buttons & B else "Released")
        try:
            self.gamepad.set_buttons(buttons)
        except Exception as exc:
            self.labels["Device"].setText(f"Virtual gamepad error: {exc}")
            self.gamepad.close()
            self.gamepad = NullGamepad()

    def check_timeout(self):
        if self.peer is not None and time.monotonic() - self.last_packet >= TIMEOUT_S:
            self.apply_buttons(0)
            self.peer = None
            self.sequence = None
            self.labels["Source"].setText("Waiting for board")

    def closeEvent(self, event):
        self.timer.stop()
        self.notifier.setEnabled(False)
        self.discovery.close()
        self.apply_buttons(0)
        self.gamepad.close()
        self.socket.close()
        super().closeEvent(event)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5004)
    args = parser.parse_args()
    application = QApplication(sys.argv)
    try:
        window = Window(args.port)
    except OSError as exc:
        print(f"Cannot start receiver: {exc}", file=sys.stderr)
        return 1
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
