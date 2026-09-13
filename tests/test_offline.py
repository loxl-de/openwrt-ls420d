#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('offline_network', REPO/'scripts/check-offline-network.py')
NETWORK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NETWORK)


class OfflineNetworkTests(unittest.TestCase):
    def test_only_active_loopback_is_accepted(self):
        NETWORK.validate_interfaces([{'ifname': 'lo', 'flags': ['LOOPBACK', 'UP']}])

    def test_down_loopback_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fakeroot'):
            NETWORK.validate_interfaces([{'ifname': 'lo', 'flags': ['LOOPBACK']}])

    def test_external_interface_or_missing_loopback_is_rejected(self):
        for interfaces in [[], [{'ifname': 'eth0', 'flags': ['UP']}],
                           [{'ifname': 'lo', 'flags': ['UP']}, {'ifname': 'eth0'}]]:
            with self.subTest(interfaces=interfaces), self.assertRaises(ValueError):
                NETWORK.validate_interfaces(interfaces)


if __name__ == '__main__':
    unittest.main()
