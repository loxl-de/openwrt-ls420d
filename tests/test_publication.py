#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class PublicationAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              capture_output=True)

    def add(self, name, content):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        self.git('add', '-f', '--', name)

    def audit(self):
        return subprocess.run([sys.executable, str(REPO/'scripts/audit-public-tree.py'),
                               '--repo', str(self.root)], capture_output=True)

    def test_clean_tree(self):
        self.add('README.md', b'Public text\n')
        self.assertEqual(self.audit().returncode, 0)

    def test_root_and_nested_credential_paths(self):
        for name in ('id_ed25519', '.env.production', 'sub/.env',
                     'authorized_keys', 'dropbear_rsa_host_key',
                     'private/site.json', 'sub/id_rsa', 'data.sqlite3', 'old/initrd.buffalo'):
            with self.subTest(name=name):
                self.add(name, b'innocent text')
                self.assertNotEqual(self.audit().returncode, 0)
                self.git('rm', '-q', '-f', '--', name)

    def test_value_and_filename_never_leaked(self):
        secret = b'gh' + b'p_' + b'AbCd0123456789' * 3
        name = secret.decode() + '\n::error::private.txt'
        self.add(name, b'prefix ' + secret + b' suffix\n')
        result = self.audit()
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertNotIn(b'::error::', result.stdout + result.stderr)

    def test_no_file_or_parent_symlink_reads(self):
        self.add('sub/data.txt', b'normal')
        (self.root/'sub/data.txt').unlink()
        (self.root/'sub').rmdir()
        (self.root/'outside').mkdir()
        (self.root/'outside/data.txt').write_bytes(b'not tracked')
        (self.root/'sub').symlink_to(self.root/'outside', target_is_directory=True)
        self.assertEqual(self.audit().returncode, 1)

    def test_tracked_symlink(self):
        (self.root/'link').symlink_to('/nonexistent')
        self.git('add', 'link')
        self.assertEqual(self.audit().returncode, 1)

    def test_missing_file_fails_closed(self):
        self.add('file.txt', b'normal')
        (self.root/'file.txt').unlink()
        self.assertEqual(self.audit().returncode, 1)

    def test_binary_fails_closed(self):
        self.add('innocent.txt', b'header\0binary')
        self.assertEqual(self.audit().returncode, 1)

    @unittest.skipUnless(shutil.which('gitleaks') or os.environ.get('GITLEAKS'),
                         'pinned Gitleaks required for history integration test')
    def test_deleted_historical_secret_detected_without_output(self):
        (self.root/'scripts').mkdir()
        shutil.copy(REPO/'scripts/scan-secrets.sh', self.root/'scripts/scan-secrets.sh')
        secret = b'gh' + b'p_' + b'AbCd0123456789' * 3
        self.add('settings.txt', b'token = "' + secret + b'"\n')
        self.git('commit', '-qm', 'fixture')
        self.git('rm', '-q', 'settings.txt')
        self.git('commit', '-qm', 'remove fixture')
        result = subprocess.run(['sh', str(self.root/'scripts/scan-secrets.sh')],
                                capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(secret, result.stdout + result.stderr)

class CompileEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root/'artifacts'
        self.source.mkdir()
        import importlib.util
        spec = importlib.util.spec_from_file_location('evidence', REPO/'scripts/compile-evidence.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        for name in set(self.module.PRODUCTS + self.module.TEXT):
            (self.source/name).write_bytes(b'public fixture\n')
        (self.source/'uImage.buffalo').write_bytes(bytes(range(256)))
        self.output = self.root/'output'

    def test_only_allowlisted_text_is_exported(self):
        (self.source/'private.bin').write_bytes(b'not public')
        self.module.export(self.source, self.output)
        self.assertFalse((self.output/'uImage.buffalo').exists())
        self.assertFalse((self.output/'initrd.buffalo').exists())
        self.assertFalse((self.output/'private.bin').exists())
        self.assertIn('uImage.buffalo', (self.output/'products.sha256').read_text())
        self.assertTrue((self.output/'GPL-2.0.txt').is_file())
        self.assertTrue((self.output/'EVIDENCE-SHA256SUMS').is_file())

    def test_missing_product_rejected(self):
        (self.source/'uImage.buffalo').unlink()
        with self.assertRaises(ValueError):
            self.module.export(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_secret_report_rejected_before_output(self):
        (self.source/'packages.manifest').write_bytes(b'gh' + b'p_' + b'AbCd0123456789' * 3)
        with self.assertRaises(ValueError):
            self.module.export(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_output_not_overwritten(self):
        self.output.mkdir()
        with self.assertRaises(ValueError):
            self.module.export(self.source, self.output)

    def test_symlinked_product_rejected(self):
        (self.source/'uImage.buffalo').unlink()
        (self.source/'uImage.buffalo').symlink_to(self.source/'initrd.buffalo')
        with self.assertRaises(ValueError):
            self.module.export(self.source, self.output)

    def test_workflow_uploads_no_firmware_directory(self):
        workflow = (REPO/'.github/workflows/ci.yml').read_text()
        self.assertNotIn('path: |\n            build/artifacts-', workflow)
        self.assertIn('path: build/evidence-', workflow)
        self.assertIn('cmp build-a/products.sha256 build-b/products.sha256', workflow)
        self.assertEqual(workflow.count('uses: actions/checkout@'),
                         workflow.count('persist-credentials: false'))


if __name__ == '__main__':
    unittest.main()
