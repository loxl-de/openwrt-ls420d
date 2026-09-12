# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import tarfile
import unittest

import test_stage_candidate as fixtures

SPEC = importlib.util.spec_from_file_location(
    'package_release_candidate', Path(__file__).resolve().parents[1] /
    'scripts/package-release-candidate.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class ReleaseCandidateTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CandidateTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.artifacts = self.fixture.artifacts
        self.sources = self.fixture.sources
        self.output = self.fixture.output
        (self.sources / 'THIRD-PARTY-NOTICES.tar').write_bytes(b'Fixture original notices')
        (self.sources / 'SHA256SUMS').write_text(''.join(
            f'{MOD.STAGE.checksum(p)}  {p.name}\n'
            for p in sorted(self.sources.iterdir()) if p.name != 'SHA256SUMS'))

    def test_packages_sources_products_and_notices_without_approval_change(self):
        MOD.package(self.artifacts, self.sources, self.output)
        self.assertEqual({p.name for p in self.output.iterdir()}, {
            'uImage.buffalo', 'initrd.buffalo', 'sources.tar', 'THIRD-PARTY-NOTICES.tar',
            'build.manifest', 'packages.manifest', 'SHA256SUMS'})
        with tarfile.open(self.output / 'sources.tar') as archive:
            self.assertEqual(archive.extractfile('source-review.json').read(), b'test source')
            self.assertEqual(archive.extractfile('THIRD-PARTY-NOTICES.tar').read(),
                             (self.output / 'THIRD-PARTY-NOTICES.tar').read_bytes())
        self.assertEqual((self.output / 'uImage.buffalo').read_bytes(), b'uImage.buffalo')

    def test_missing_notices_rejected_before_output(self):
        (self.sources / 'THIRD-PARTY-NOTICES.tar').unlink()
        with self.assertRaises(ValueError):
            MOD.package(self.artifacts, self.sources, self.output)
        self.assertFalse(self.output.exists())

    def test_wrong_firmware_rejected_before_output(self):
        (self.artifacts / 'uImage.buffalo').write_bytes(b'Wrong build')
        with self.assertRaises(ValueError):
            MOD.package(self.artifacts, self.sources, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_preserved(self):
        self.output.mkdir()
        with self.assertRaises(ValueError):
            MOD.package(self.artifacts, self.sources, self.output)

    def test_output_under_sources_rejected(self):
        with self.assertRaises(ValueError):
            MOD.package(self.artifacts, self.sources, self.sources / 'release')
