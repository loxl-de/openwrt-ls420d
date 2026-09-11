#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import json
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
        self.assertEqual(inventory['etc/config/dropbear'], {'type': 'file'})

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
        hook = source/'files/etc/uci-defaults/50-ls420d-site'
        self.assertEqual(hook.stat().st_mode & 0o777, 0o755)
        self.assertEqual(subprocess.run(cmd, env=env, capture_output=True).returncode, 1)

if __name__ == '__main__':
    unittest.main()
