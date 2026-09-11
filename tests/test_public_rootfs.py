#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]

class PublicRootfsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base/'root'
        shutil.copytree(REPO/'openwrt/files', self.root)

    def audit(self):
        return subprocess.run([sys.executable, str(REPO/'scripts/audit-rootfs.py'),
                               str(self.root), str(self.base/'inventory.json')],
                              capture_output=True).returncode

    def test_public_defaults(self):
        self.assertEqual(self.audit(), 0)
        inventory = json.loads((self.base/'inventory.json').read_text())
        entry = inventory['etc/config/dropbear']
        self.assertEqual(entry['type'], 'file')
        self.assertEqual(entry['sha256'], hashlib.sha256((self.root/'etc/config/dropbear').read_bytes()).hexdigest())

    def test_content_changes_with_identical_names_and_sizes_are_detected(self):
        path = self.root/'etc/fixture'
        path.write_bytes(b'first')
        self.assertEqual(self.audit(), 0)
        first = json.loads((self.base/'inventory.json').read_text())
        path.write_bytes(b'other')
        self.assertEqual(self.audit(), 0)
        second = json.loads((self.base/'inventory.json').read_text())
        self.assertNotEqual(first['etc/fixture']['sha256'], second['etc/fixture']['sha256'])
        self.assertEqual(first['etc/fixture']['size'], second['etc/fixture']['size'])

    def test_timestamps_are_not_treated_as_content_changes(self):
        self.assertEqual(self.audit(), 0)
        first = (self.base/'inventory.json').read_bytes()
        path = self.root/'etc/config/dropbear'
        os.utime(path, (1, 1))
        self.assertEqual(self.audit(), 0)
        self.assertEqual(first, (self.base/'inventory.json').read_bytes())

    def test_symlink_target_is_recorded_without_reading_it(self):
        (self.root/'etc/link').symlink_to('/not-present')
        self.assertEqual(self.audit(), 0)
        entry = json.loads((self.base/'inventory.json').read_text())['etc/link']
        self.assertEqual(entry['target'], '/not-present')
        self.assertNotIn('sha256', entry)

    def test_extra_enabled_section_rejected(self):
        with (self.root/'etc/config/dropbear').open('a') as stream:
            stream.write("\nconfig dropbear\n option enable '1'\n")
        self.assertNotEqual(self.audit(), 0)

    def test_host_key_rejected(self):
        (self.root/'etc/dropbear').mkdir()
        (self.root/'etc/dropbear/dropbear_ed25519_host_key').write_bytes(b'fixture')
        self.assertNotEqual(self.audit(), 0)

    def test_client_authorization_rejected(self):
        (self.root/'root/.ssh').mkdir(parents=True)
        (self.root/'root/.ssh/authorized_keys').touch()
        self.assertNotEqual(self.audit(), 0)

    def test_config_symlink_rejected(self):
        path = self.root/'etc/config/dropbear'
        path.unlink()
        path.symlink_to(REPO/'openwrt/files/etc/config/dropbear')
        self.assertNotEqual(self.audit(), 0)

    def test_public_overlay_install_permissions_and_no_replace(self):
        source = self.base/'source'
        source.mkdir()
        import os
        env = dict(os.environ, OPENWRT_SOURCE_DIR=str(source))
        cmd = ['sh', str(REPO/'scripts/install-public-files.sh')]
        self.assertEqual(subprocess.run(cmd, env=env, capture_output=True).returncode, 0)
        worker = source/'files/usr/sbin/ls420d-fan'
        self.assertEqual(worker.stat().st_mode & 0o777, 0o755)
        self.assertEqual(subprocess.run(cmd, env=env, capture_output=True).returncode, 1)

if __name__ == '__main__':
    unittest.main()
