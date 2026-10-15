"""Exercise discovery over real UDP sockets; run with python -m unittest."""

import socket
import unittest

from discovery import ANNOUNCEMENT, MAGIC, QUERY, HostDiscovery


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client.bind(("127.0.0.1", 0))
        self.client.settimeout(0.5)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]

    def tearDown(self):
        self.client.close()

    def test_probe_advertises_actual_receiver_port(self):
        with HostDiscovery(54321, discovery_port=self.port):
            self.client.sendto(QUERY, ("127.0.0.1", self.port))
            payload, source = self.client.recvfrom(64)
            self.assertEqual(payload, b"HWH\x01\xd4\x31\x00\x00")
            self.assertEqual(source, ("127.0.0.1", self.port))

    def test_ignores_wrong_version_and_malformed_queries(self):
        with HostDiscovery(5004, discovery_port=self.port):
            for data in (b"HW?\x02", QUERY + b"extra", b"HWH\x01", b""):
                self.client.sendto(data, ("127.0.0.1", self.port))

            with self.assertRaises(socket.timeout):
                self.client.recvfrom(64)

    def test_close_releases_port_and_restart_changes_advertised_port(self):
        for receiver_port in (5004, 5014):
            with HostDiscovery(receiver_port, discovery_port=self.port):
                self.client.sendto(QUERY, ("127.0.0.1", self.port))
                payload, _ = self.client.recvfrom(64)
                self.assertEqual(ANNOUNCEMENT.unpack(payload), (MAGIC, receiver_port))

    def test_second_receiver_cannot_silently_share_discovery(self):
        with HostDiscovery(5004, discovery_port=self.port):
            with self.assertRaises(OSError):
                HostDiscovery(5014, discovery_port=self.port)


if __name__ == "__main__":
    unittest.main()
