#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]


class FdtgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ)
        self.env.pop('FDTGET', None)
        self.env['PATH'] = str(self.root)
        self.lib = REPO/'scripts/lib.sh'

    def tool(self, name='fdtget', status=0):
        path = self.root/name
        path.write_text('#!/bin/sh\n'
                        '[ "$#" -eq 1 ] && [ "$1" = --version ] || exit 91\n'
                        f'printf "fixture fdtget\\n"\nexit {status}\n')
        path.chmod(0o755)
        return path

    def check(self):
        return subprocess.run(['/bin/sh', '-c', '. "$1"; check_fdtget',
                               'test', str(self.lib)], env=self.env,
                              text=True, capture_output=True, timeout=10)

    def test_default_uses_path_without_openwrt_staging(self):
        self.tool()
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('fixture fdtget', result.stdout)

    def test_explicit_path_with_spaces(self):
        self.env['FDTGET'] = str(self.tool('custom fdtget'))
        self.assertEqual(self.check().returncode, 0)

    def test_missing_tool_fails(self):
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('required command not found: fdtget', result.stderr)

    def test_missing_override_does_not_fall_back(self):
        self.tool()
        self.env['FDTGET'] = str(self.root/'missing')
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('required command not found:', result.stderr)

    def test_broken_executable_fails(self):
        self.tool(status=7)
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('fdtget is not runnable:', result.stderr)

    def test_build_and_packaging_fail_before_accessing_source(self):
        project = self.root/'project'
        (project/'scripts').mkdir(parents=True)
        (project/'config').mkdir()
        (project/'config/ls420d.config').write_text('fixture\n')
        for name in ('lib.sh', 'build.sh', 'package-buffalo.sh'):
            shutil.copy2(REPO/'scripts'/name, project/'scripts'/name)
        env = dict(os.environ, FDTGET=str(self.root/'missing'),
                   SOURCE_DATE_EPOCH='123456789',
                   OPENWRT_SOURCE_DIR=str(self.root/'must-not-be-created'))
        for key in ('OPENWRT_CONFIG', 'ROOTFS_OVERLAY', 'DEPLOYMENT_CONFIG',
                    'SITE_DIR', 'SECRETS_DIR'):
            env.pop(key, None)
        for script in ('build.sh', 'package-buffalo.sh'):
            with self.subTest(script=script):
                result = subprocess.run(['/bin/sh', str(project/'scripts'/script)],
                                        env=env, text=True, capture_output=True,
                                        timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('required command not found:', result.stderr)
                self.assertNotIn('not a git repository', result.stderr)
                self.assertFalse(Path(env['OPENWRT_SOURCE_DIR']).exists())


if __name__ == '__main__':
    unittest.main()
