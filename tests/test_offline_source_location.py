# SPDX-License-Identifier: MIT
"""Exercise the actual workflow relocation step without starting a build."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class OfflineSourceLocationTests(unittest.TestCase):
    def test_default_relocation_and_existing_target(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    '.github/workflows/offline-source.yml').read_text()
        section = workflow.split('      - name: Select the controlled source location\n', 1)[1]
        block = section.split('        run: |\n', 1)[1].split('      - name:', 1)[0]
        script = '\n'.join(line[10:] for line in block.splitlines())
        for mode in ('default', 'relocate', 'occupied'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                workspace = root/'workspace'
                workspace.mkdir()
                temporary = root/'temporary'
                source = temporary/'offline-source/openwrt'
                source.mkdir(parents=True)
                (source/'proof').touch()
                destination = workspace/'openwrt-src'
                if mode == 'occupied':
                    destination.mkdir()
                envfile = root/'environment'
                envfile.touch()
                env = dict(os.environ, RUNNER_TEMP=str(temporary),
                           GITHUB_WORKSPACE=str(workspace), GITHUB_ENV=str(envfile),
                           SAME_WORKSPACE_PATH='false' if mode == 'default' else 'true')
                result = subprocess.run(['bash', '-e', '-c', script], env=env,
                                        capture_output=True, text=True)
                if mode == 'occupied':
                    self.assertNotEqual(result.returncode, 0)
                    self.assertTrue((source/'proof').exists())
                    self.assertEqual(envfile.read_text(), '')
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    expected = source if mode == 'default' else destination
                    self.assertTrue((expected/'proof').exists())
                    if mode == 'relocate':
                        self.assertEqual(envfile.read_text(),
                                         f'OFFLINE_SOURCE_OVERRIDE={destination}\n')


if __name__ == '__main__':
    unittest.main()
