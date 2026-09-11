#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile
import test_source_review as fixtures


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('source_restore', REPO/'scripts/restore-source-review.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceRestoreTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SourceReviewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.collect()
        self.archive = self.fixture.root/'source.zip'
        self.output = self.fixture.root/'restored'
        with zipfile.ZipFile(self.archive, 'w') as z:
            for path in self.fixture.output.iterdir():
                z.write(path, path.name)
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def test_round_trip_restores_source_and_downloads_without_git(self):
        MODULE.restore(self.archive, self.digest, self.output)
        self.assertEqual((self.output/'project/README').read_text(), 'Committed source\n')
        self.assertEqual((self.output/'downloads/dl/source.tar.gz').read_bytes(), b'Fixture compressed source')
        self.assertFalse(list(self.output.rglob('.git')))
        self.assertTrue((self.output/'RESTORED.json').is_file())

    def test_wrong_external_digest_fails_before_writes(self):
        with self.assertRaises(ValueError):
            MODULE.restore(self.archive, '0'*64, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_destination_is_not_modified(self):
        self.output.mkdir()
        with self.assertRaises(ValueError):
            MODULE.restore(self.archive, self.digest, self.output)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_missing_member_fails_before_writes(self):
        truncated = self.fixture.root/'incomplete.zip'
        with zipfile.ZipFile(truncated, 'w') as z:
            z.writestr('README.txt', 'incomplete')
        with self.assertRaises(ValueError):
            MODULE.restore(truncated, hashlib.sha256(truncated.read_bytes()).hexdigest(), self.output)
        self.assertFalse(self.output.exists())

    def make_tar(self, members):
        archive = self.fixture.root/'fixture.tar'
        with tarfile.open(archive, 'w') as tar:
            for name, target in members:
                info = tarfile.TarInfo(name)
                if target is not None:
                    info.type = tarfile.SYMTYPE
                    info.linkname = target
                    tar.addfile(info)
                else:
                    info.size = 4
                    tar.addfile(info, io.BytesIO(b'data'))
        return archive

    def test_confined_relative_symlink_is_preserved(self):
        archive = self.make_tar([('a/data', None), ('b/link', '../a/data')])
        MODULE.extract_tree(archive, self.output)
        self.assertTrue((self.output/'b/link').is_symlink())
        self.assertEqual((self.output/'b/link').read_bytes(), b'data')

    def test_escaping_paths_links_and_git_metadata_are_rejected(self):
        for members in [[('../outside', None)], [('/outside', None)],
                        [('link', '../outside')], [('link', '/outside')],
                        [('.git/config', None)], [('a', None), ('a/child', None)],
                        [('a', None), ('a', None)],
                        [('a', 'b'), ('a/child', None)]]:
            with self.subTest(members=members):
                archive = self.make_tar(members)
                with self.assertRaises(ValueError):
                    MODULE.extract_tree(archive, self.output)
                self.assertFalse(self.output.exists())

    def test_checksum_mismatch_fails_before_writes(self):
        corrupt = self.fixture.root/'corrupt.zip'
        with zipfile.ZipFile(self.archive) as original, zipfile.ZipFile(corrupt, 'w') as z:
            for name in original.namelist():
                z.writestr(name, b'changed' if name == 'project.tar' else original.read(name))
        with self.assertRaises(ValueError):
            MODULE.restore(corrupt, hashlib.sha256(corrupt.read_bytes()).hexdigest(), self.output)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
