#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
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


class MakeDiagnosticsTests(unittest.TestCase):
    def run_mock(self, first, second=0):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mock = root/'make'
            mock.write_text('#!/bin/sh\n'
                            'printf "%s\\n" "$*" >> "$MOCK_LOG"\n'
                            'if [ -e "$MOCK_STAMP" ]; then exit "$MOCK_SECOND"; fi\n'
                            'touch "$MOCK_STAMP"\nexit "$MOCK_FIRST"\n')
            mock.chmod(0o755)
            env = dict(os.environ, PATH=str(root)+os.pathsep+os.environ['PATH'],
                       MOCK_LOG=str(root/'calls'), MOCK_STAMP=str(root/'stamp'),
                       MOCK_FIRST=str(first), MOCK_SECOND=str(second))
            result = subprocess.run(['sh', str(REPO/'scripts/make-with-diagnostics.sh'),
                                     '-C', '/path with spaces', '-j4', 'download'],
                                    env=env, capture_output=True, text=True)
            return result, (root/'calls').read_text().splitlines()

    def test_success_is_not_repeated(self):
        result, calls = self.run_mock(0)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1)

    def test_serial_success_does_not_hide_parallel_failure(self):
        result, calls = self.run_mock(2)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(calls, ['-C /path with spaces -j4 download',
                                 '-C /path with spaces -j4 download -j1 V=s'])

    def test_original_failure_status_survives_failed_diagnostic(self):
        result, calls = self.run_mock(2, 7)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(calls), 2)


if __name__ == '__main__':
    unittest.main()
