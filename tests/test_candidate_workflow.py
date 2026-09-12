# SPDX-License-Identifier: MIT
from pathlib import Path
import unittest


class CandidateWorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.text = (Path(__file__).resolve().parents[1] /
                     '.github/workflows/candidate.yml').read_text()

    def test_only_manual_main_branch_can_run(self):
        self.assertIn('on:\n  workflow_dispatch:\n', self.text)
        for trigger in ('pull_request:', 'pull_request_target:', 'push:', 'schedule:', 'workflow_run:'):
            self.assertNotIn(trigger, self.text)
        self.assertIn("if: github.repository == 'loxl-de/openwrt-ls420d' && github.ref == 'refs/heads/main'",
                      self.text)
        self.assertIn('persist-credentials: false', self.text)

    def test_retains_draft_without_public_firmware_artifacts(self):
        self.assertIn('--target "$GITHUB_SHA" --draft --prerelease', self.text)
        self.assertNotIn('release edit', self.text)
        self.assertNotIn('--draft=false', self.text)
        self.assertNotIn('actions/upload-artifact', self.text)
        self.assertNotIn('--clobber', self.text)
        self.assertEqual(self.text.count('--json isDraft --jq .isDraft'), 3)

    def test_sources_and_notices_are_uploaded_with_firmware(self):
        for name in ('uImage.buffalo', 'initrd.buffalo', 'sources.tar',
                     'THIRD-PARTY-NOTICES.tar', 'build.manifest',
                     'packages.manifest', 'SHA256SUMS'):
            self.assertIn('build/release/' + name, self.text)
        self.assertIn('--notice-selection config/notice-files.json', self.text)

    def test_sources_finish_uploading_before_firmware(self):
        self.assertEqual(self.text.count('gh release upload'), 2)
        self.assertLess(self.text.index('build/release/sources.tar'),
                        self.text.index('build/release/uImage.buffalo'))

    def test_access_checked_before_expensive_build(self):
        self.assertLess(self.text.index('gh release create'), self.text.index('run: ./scripts/build.sh'))
        self.assertIn('cancel-in-progress: false', self.text)
        self.assertIn('runs-on: ubuntu-24.04', self.text)
        self.assertIn('zstd busybox shellcheck', self.text)
