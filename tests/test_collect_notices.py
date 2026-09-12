# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'collect_notices', Path(__file__).resolve().parents[1] / 'scripts/collect-notices.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class NoticeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / 'notices.tar'
        self.source = self.root / 'source.tar'
        self.blob = b'Copyright example\r\nOriginal license bytes.\n'
        self.make_archive()
        self.selection = {'files': [{'source': 'source.tar',
            'source_sha256': MOD.digest(self.source), 'member': 'src/LICENSE',
            'sha256': hashlib.sha256(self.blob).hexdigest()}]}

    def make_archive(self, duplicate=False, link=False):
        with tarfile.open(self.source, 'w') as archive:
            for _ in range(2 if duplicate else 1):
                info = tarfile.TarInfo('src/LICENSE')
                if link:
                    info.type, info.linkname = tarfile.SYMTYPE, '/etc/passwd'
                    archive.addfile(info)
                else:
                    info.size = len(self.blob)
                    archive.addfile(info, io.BytesIO(self.blob))

    def run_collect(self):
        MOD.collect(self.root, self.selection, self.output)

    def test_preserves_bytes_and_is_repeatable(self):
        self.run_collect()
        with tarfile.open(self.output) as archive:
            self.assertEqual(archive.extractfile('notices/source.tar/src/LICENSE').read(), self.blob)
        second = self.root / 'second.tar'
        MOD.collect(self.root, self.selection, second)
        self.assertEqual(MOD.digest(self.output), MOD.digest(second))

    def test_bad_archive_hash(self):
        self.selection['files'][0]['source_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.run_collect()
        self.assertFalse(self.output.exists())

    def test_bad_member_hash(self):
        self.selection['files'][0]['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.run_collect()

    def test_missing_member(self):
        self.selection['files'][0]['member'] = 'src/MISSING'
        with self.assertRaises(ValueError):
            self.run_collect()

    def test_duplicate_selection(self):
        self.selection['files'] *= 2
        with self.assertRaises(ValueError):
            self.run_collect()

    def test_duplicate_archive_member(self):
        self.make_archive(duplicate=True)
        self.selection['files'][0]['source_sha256'] = MOD.digest(self.source)
        with self.assertRaises(ValueError):
            self.run_collect()

    def test_archive_symlink(self):
        self.make_archive(link=True)
        self.selection['files'][0]['source_sha256'] = MOD.digest(self.source)
        with self.assertRaises(ValueError):
            self.run_collect()

    def test_unsafe_paths(self):
        for key, value in [('source', '../source.tar'), ('member', '../LICENSE'),
                           ('member', '/LICENSE'), ('member', 'src//LICENSE')]:
            with self.subTest(key=key, value=value):
                original = self.selection['files'][0][key]
                self.selection['files'][0][key] = value
                with self.assertRaises(ValueError):
                    self.run_collect()
                self.selection['files'][0][key] = original

    def test_existing_output_is_preserved(self):
        self.output.write_bytes(b'keep')
        with self.assertRaises(ValueError):
            self.run_collect()
        self.assertEqual(self.output.read_bytes(), b'keep')
