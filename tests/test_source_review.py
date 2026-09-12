#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('source_review', REPO/'scripts/collect-source-review.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root/'project'
        self.source = self.root/'openwrt'
        self.downloads = self.root/'dl'
        self.artifacts = self.root/'artifacts'
        self.output = self.root/'review'
        for path in (self.repo, self.source, self.downloads, self.artifacts):
            path.mkdir()
        self.source_commit = self.make_repo(self.source)
        (self.source/'.git/ls420d-managed').touch()
        feeds = []
        for name in sorted(MODULE.FEEDS):
            path = self.source/'feeds'/name
            path.mkdir(parents=True)
            commit = self.make_repo(path)
            feeds.append(f'{name}|https://example.invalid/{name}.git|{commit}\n')
        (self.repo/'openwrt.lock').write_text(f'OPENWRT_COMMIT={self.source_commit}\n')
        (self.repo/'feeds.lock').write_text(''.join(feeds))
        (self.repo/'LICENSE').write_text('Fixture license\n')
        self.project_commit = self.make_repo(self.repo)
        (self.source/'.config').write_text('CONFIG_TARGET_mvebu=y\n')
        kernel = self.source/'build_dir/target-arm/linux-mvebu/linux-6.12.94'
        kernel.mkdir(parents=True)
        (kernel/'.config').write_text('CONFIG_ARM=y\n')
        (self.source/'tmp').mkdir()
        for name in ('.packageinfo', '.targetinfo'):
            (self.source/'tmp'/name).write_text('Fixture metadata\n')
        for name in ('packages.manifest', 'build.manifest', 'upstream-delta.patch', 'runner.txt'):
            (self.artifacts/name).write_text('Fixture metadata\n')
        (self.artifacts/'build.manifest').write_text(
            f'REPOSITORY_COMMIT={self.project_commit}\n'
            f'OPENWRT_COMMIT={self.source_commit}\n'
            f'CONFIG_SHA256={MODULE.digest(self.source/".config")}\n'
            f'SOURCE_DATE_EPOCH={self.git(self.source, "show", "-s", "--format=%ct")}\n')
        (self.artifacts/'uImage.buffalo').write_bytes(b'Not source material')
        (self.downloads/'source.tar.gz').write_bytes(b'Fixture compressed source')

    def make_repo(self, path):
        self.git(path, 'init', '-q')
        self.git(path, 'config', 'user.name', 'Source Fixture')
        self.git(path, 'config', 'user.email', 'source@example.invalid')
        (path/'README').write_text('Committed source\n')
        self.git(path, 'add', '.')
        self.git(path, 'commit', '-qm', 'fixture')
        return self.git(path, 'rev-parse', 'HEAD')

    def git(self, path, *args):
        return subprocess.check_output(['git', '-C', str(path), *args],
                                       stderr=subprocess.PIPE).decode().strip()

    def collect(self):
        MODULE.collect(self.repo, self.source, self.downloads, self.artifacts, self.output)

    def test_complete_candidate_excludes_build_outputs_and_git_metadata(self):
        (self.source/'untracked-private-file').write_text('Must not be archived')
        self.collect()
        report = json.loads((self.output/'source-review.json').read_text())
        self.assertEqual(report['project_commit'], self.project_commit)
        self.assertEqual(report['openwrt_commit'], self.source_commit)
        self.assertFalse(report['offline_rebuild_verified'])
        self.assertFalse(report['license_review_complete'])
        self.assertFalse(report['firmware_distribution_authorized'])
        self.assertEqual(set(report['feed_commits']), MODULE.FEEDS)
        with tarfile.open(self.output/'openwrt-upstream.tar') as archive:
            self.assertEqual(archive.getnames(), ['README'])
        with tarfile.open(self.output/'downloads.tar') as archive:
            self.assertEqual(archive.getnames(), ['dl/source.tar.gz'])
        self.assertFalse((self.output/'uImage.buffalo').exists())
        for line in (self.output/'SHA256SUMS').read_text().splitlines():
            checksum, name = line.split(maxsplit=1)
            self.assertEqual(hashlib.sha256((self.output/name).read_bytes()).hexdigest(), checksum)

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output/'sentinel'
        sentinel.write_text('keep')
        with self.assertRaises(ValueError):
            self.collect()
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_download_symlink_is_rejected_before_output(self):
        (self.downloads/'unexpected.tar.gz').symlink_to(self.repo/'README')
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse(self.output.exists())

    def test_download_parent_symlink_is_rejected(self):
        alias = self.root/'alias'
        alias.symlink_to(self.downloads, target_is_directory=True)
        with self.assertRaises(ValueError):
            MODULE.download_inputs(alias)

    def test_unexpected_download_is_not_silently_omitted(self):
        (self.downloads/'unknown.bin').write_bytes(b'Unknown input')
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse(self.output.exists())

    def test_missing_config_is_rejected_before_output(self):
        (self.source/'.config').unlink()
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse(self.output.exists())

    def test_dirty_project_is_rejected(self):
        (self.repo/'README').write_text('Uncommitted change')
        with self.assertRaises(ValueError):
            self.collect()

    def test_wrong_git_revision_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.archive_git(self.repo, '0'*40, self.output)
        self.assertFalse(self.output.exists())

    def test_manifest_from_another_build_is_rejected(self):
        (self.artifacts/'build.manifest').write_text('REPOSITORY_COMMIT='+'0'*40+'\n')
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse(self.output.exists())

    def test_config_changed_after_build_is_rejected(self):
        (self.source/'.config').write_text('CONFIG_WRONG=y\n')
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse(self.output.exists())

    def test_empty_download_directory_is_rejected(self):
        (self.downloads/'source.tar.gz').unlink()
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse(self.output.exists())

    def test_git_archive_is_repeatable(self):
        first, second = self.root/'a.tar', self.root/'b.tar'
        MODULE.archive_git(self.repo, self.project_commit, first)
        MODULE.archive_git(self.repo, self.project_commit, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_notices_are_collected_and_checksums_cover_them(self):
        archive_path = self.downloads/'source.tar.gz'
        with tarfile.open(archive_path, 'w:gz') as archive:
            blob = b'Original fixture notice\\n'
            info = tarfile.TarInfo('source/LICENSE')
            info.size = len(blob)
            archive.addfile(info, io.BytesIO(blob))
        selection = self.root/'notice-selection.json'
        selection.write_text('{"files": []}')
        MODULE.collect(self.repo, self.source, self.downloads, self.artifacts,
                       self.output, selection)
        with tarfile.open(self.output/'THIRD-PARTY-NOTICES.tar') as archive:
            self.assertEqual(
                archive.extractfile('notices/source.tar.gz/source/LICENSE').read(), blob)
        sums = (self.output/'SHA256SUMS').read_text()
        self.assertIn(MODULE.digest(self.output/'THIRD-PARTY-NOTICES.tar')
                      + '  THIRD-PARTY-NOTICES.tar', sums)
        self.assertFalse(json.loads((self.output/'source-review.json').read_text())
                         ['firmware_distribution_authorized'])

    def test_notice_failure_leaves_no_completion_inventory(self):
        selection = self.root/'notice-selection.json'
        selection.write_text('{"files": []}')
        # The default fixture is deliberately not a valid compressed tar.
        with self.assertRaises(subprocess.CalledProcessError):
            MODULE.collect(self.repo, self.source, self.downloads, self.artifacts,
                           self.output, selection)
        self.assertFalse((self.output/'SHA256SUMS').exists())


if __name__ == '__main__':
    unittest.main()
