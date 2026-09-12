# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'stage_candidate', Path(__file__).resolve().parents[1] / 'scripts/stage-candidate.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.artifacts, self.sources, self.output = (root / n for n in ('artifacts', 'sources', 'candidate'))
        self.artifacts.mkdir()
        self.sources.mkdir()
        fields = []
        for name in ('uImage.buffalo', 'initrd.buffalo', 'packages.manifest'):
            payload = name.encode()
            (self.artifacts / name).write_bytes(payload)
            fields.append(f'ARTIFACT_SHA256[{name}]={hashlib.sha256(payload).hexdigest()}')
        (self.artifacts / 'build.manifest').write_text('\n'.join(fields) + '\n')
        names = ['project.tar', 'openwrt-upstream.tar', 'downloads.tar',
                 'source-review.json', 'openwrt.config', 'linux.config', 'PROJECT-LICENSE.txt']
        names += [f'feed-{n}.tar' for n in ('packages', 'luci', 'routing', 'telephony', 'video')]
        for name in names:
            (self.sources / name).write_text('test source')
        for name in ('build.manifest', 'packages.manifest'):
            (self.sources / name).write_bytes((self.artifacts / name).read_bytes())
        (self.sources / 'SHA256SUMS').write_text(''.join(
            f'{MOD.checksum(p)}  {p.name}\n' for p in sorted(self.sources.iterdir())))

    def test_pair_preserves_products_sources_and_review_state(self):
        MOD.stage(self.artifacts, self.sources, self.output)
        self.assertEqual((self.output / 'initrd.buffalo').read_bytes(), b'initrd.buffalo')
        self.assertEqual((self.output / 'sources/source-review.json').read_text(), 'test source')
        self.assertIn('sources/downloads.tar', (self.output / 'SHA256SUMS').read_text())

    def test_tampered_source_rejected_before_output(self):
        (self.sources / 'project.tar').write_text('changed')
        with self.assertRaises(ValueError):
            MOD.stage(self.artifacts, self.sources, self.output)
        self.assertFalse(self.output.exists())

    def test_wrong_firmware_rejected(self):
        (self.artifacts / 'uImage.buffalo').write_text('other build')
        with self.assertRaises(ValueError):
            MOD.stage(self.artifacts, self.sources, self.output)

    def test_unlisted_file_rejected(self):
        (self.sources / 'private.key').write_text('test only')
        with self.assertRaises(ValueError):
            MOD.stage(self.artifacts, self.sources, self.output)

    def test_existing_output_preserved(self):
        self.output.mkdir()
        with self.assertRaises(ValueError):
            MOD.stage(self.artifacts, self.sources, self.output)

    def test_symlink_product_rejected(self):
        (self.artifacts / 'uImage.buffalo').unlink()
        (self.artifacts / 'uImage.buffalo').symlink_to(self.artifacts / 'initrd.buffalo')
        with self.assertRaises(ValueError):
            MOD.stage(self.artifacts, self.sources, self.output)

    def test_duplicate_inventory_entry_rejected(self):
        path = self.sources / 'SHA256SUMS'
        path.write_text(path.read_text() + path.read_text().splitlines()[0] + '\n')
        with self.assertRaises(ValueError):
            MOD.stage(self.artifacts, self.sources, self.output)

    def test_missing_required_source_rejected(self):
        path = self.sources / 'SHA256SUMS'
        path.write_text(''.join(line + '\n' for line in path.read_text().splitlines()
                                if not line.endswith('  downloads.tar')))
        (self.sources / 'downloads.tar').unlink()
        with self.assertRaises(ValueError):
            MOD.stage(self.artifacts, self.sources, self.output)

    def test_mutation_during_copy_leaves_no_completion_inventory(self):
        from unittest.mock import patch
        original = MOD.shutil.copyfile

        def changed_copy(src, dst, **kwargs):
            result = original(src, dst, **kwargs)
            if Path(dst) == self.output / 'uImage.buffalo':
                Path(dst).write_text('changed during copy')
            return result

        with patch.object(MOD.shutil, 'copyfile', side_effect=changed_copy):
            with self.assertRaises(ValueError):
                MOD.stage(self.artifacts, self.sources, self.output)
        self.assertFalse((self.output / 'SHA256SUMS').exists())
