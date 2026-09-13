# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'repro_build_inputs', REPO/'scripts/repro_build_inputs.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BuildInputEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ls420d-private-build-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root/'openwrt-src'
        (self.source/'staging_dir/host/bin').mkdir(parents=True)
        (self.source/'staging_dir/toolchain-fixture/bin').mkdir(parents=True)
        gcc = self.source/'staging_dir/host/bin/gcc'
        gcc.write_text('#!/bin/sh\nprintf "gcc (fixture) 14.3.0\\\\n"\n')
        gcc.chmod(0o755)
        target = self.source/'staging_dir/toolchain-fixture/bin/arm-openwrt-linux-gcc'
        target.write_text('#!/bin/sh\nprintf "arm-openwrt-linux-gcc (fixture) 14.3.0\\\\n"\n')
        target.chmod(0o755)
        self.system_bin = self.root/'system/bin'
        self.system_bin.mkdir(parents=True)
        for name in ('gcc', 'g++', 'ld'):
            path = self.system_bin/name
            path.write_text(f'#!/bin/sh\nprintf "system-{name} 99.0\\\\n"\n')
            path.chmod(0o755)
        (self.source/'.config').write_text('PRIVATE_CONFIG_MARKER=y\n')
        linux = self.source/'build_dir/target-fixture/linux-mvebu/linux-6.12.94'
        linux.mkdir(parents=True)
        (linux/'.config').write_text('CONFIG_FIXTURE=y\n')
        gcc_tree = self.source/'build_dir/toolchain-fixture/gcc-14.3.0'
        (gcc_tree/'gcc').mkdir(parents=True)
        (gcc_tree/'libstdc++-v3').mkdir(parents=True)
        (gcc_tree/'gcc/config.status').write_text('PRIVATE_GENERATED_MARKER\n')
        (gcc_tree/'gcc/auto-host.h').write_text('#define FIXTURE 1\n')
        (gcc_tree/'libstdc++-v3/config.h').write_text('#define FIXTURE 2\n')
        final_libstdcxx = (self.source/'build_dir/toolchain-fixture/'
                           'gcc-14.3.0-final/arm-openwrt-linux-muslgnueabi/libstdc++-v3')
        final_libstdcxx.mkdir(parents=True)
        (final_libstdcxx/'config.status').write_text('FINAL_GENERATED_MARKER\n')
        version_date = gcc_tree/'libstdc++-v3/version.date'
        version_date.write_text('1782737960\n')
        self.output = self.root/'evidence.json'

    def collect(self, extra=None):
        environment = {
            'SOURCE_DATE_EPOCH': '1782737960',
            'JOBS': '4',
            'CCACHE_DISABLE': '1',
            'GITHUB_WORKSPACE': str(self.root/'workspace'),
            'OFFLINE_RESTORED_SOURCE_DIR': str(self.root/'restored-source'),
        }
        environment.update(extra or {})
        def which(name):
            return str(self.system_bin/name)
        with patch.dict(os.environ, environment, clear=False), \
                patch.object(MODULE.shutil, 'which', side_effect=which):
            return MODULE.collect(self.source, self.output,
                                  self.root/'work', self.root/'project')

    def test_hashes_tools_configs_and_exact_date_without_payloads(self):
        report = self.collect()
        encoded = self.output.read_text()
        self.assertNotIn('PRIVATE_CONFIG_MARKER', encoded)
        self.assertNotIn('PRIVATE_GENERATED_MARKER', encoded)
        self.assertNotIn('FINAL_GENERATED_MARKER', encoded)
        self.assertNotIn(str(self.root), encoded)
        self.assertEqual(report['source_date_epoch']['value'], 1782737960)
        self.assertEqual(report['source_date_epoch']['utc'], '2026-06-29T12:59:20+00:00')
        self.assertEqual(report['version_dates'][0]['value'], '1782737960')
        self.assertFalse(report['roots']['same_workspace_openwrt_src'])
        host = next(item for item in report['tools'] if item['role'] == 'host-gcc')
        self.assertEqual(host['status'], 'ok')
        self.assertEqual(host['version_line'], 'gcc (fixture) 14.3.0')
        self.assertEqual(host['sha256'],
                         hashlib.sha256((self.source/'staging_dir/host/bin/gcc').read_bytes()).hexdigest())
        self.assertTrue(any(item['role'] == 'generated-gcc' and
                            item['path'].endswith('gcc/config.status')
                            for item in report['configurations']))
        self.assertTrue(any(item['role'] == 'generated-libstdc++-v3' and
                            item['path'].endswith(
                                'gcc-14.3.0-final/arm-openwrt-linux-muslgnueabi/'
                                'libstdc++-v3/config.status')
                            for item in report['configurations']))
        system = {item['role']: item for item in report['tools']
                  if item['role'].startswith('system-')}
        self.assertEqual(set(system), {'system-gcc', 'system-g++', 'system-ld'})
        self.assertTrue(all(item['status'] == 'ok' for item in system.values()))
        self.assertTrue(all('path' not in item and 'path_sha256' in item
                            for item in system.values()))
        self.assertEqual(json.loads(encoded), report)

    def test_output_is_exclusive_and_epoch_is_required(self):
        self.output.write_text('keep')
        with self.assertRaises(ValueError):
            MODULE.collect(self.source, self.output)
        self.output.unlink()
        with patch.dict(os.environ, {'SOURCE_DATE_EPOCH': 'not-a-date'}, clear=False):
            with self.assertRaises(ValueError):
                MODULE.collect(self.source, self.output)
        self.assertFalse(self.output.exists())
    def test_non_numeric_scalar_and_paths_are_hashed(self):
        report = self.collect({
            'CCACHE_DISABLE': 'enabled',
            'GIT_CONFIG_NOSYSTEM': 'yes',
            'GIT_CONFIG_GLOBAL': '/private/config',
        })
        encoded = self.output.read_text()
        self.assertNotIn('enabled', encoded)
        self.assertNotIn('/private/config', encoded)
        self.assertEqual(report['environment']['CCACHE_DISABLE']['value_status'],
                         'non-numeric-hidden')
        self.assertEqual(report['environment']['GIT_CONFIG_NOSYSTEM']['value_status'],
                         'non-numeric-hidden')
        self.assertNotIn('value', report['environment']['GIT_CONFIG_GLOBAL'])

    def test_version_date_symlink_escape_and_oversize_are_rejected(self):
        outside = self.root/'outside.date'
        outside.write_text('1782737960\n')
        link = self.source/'build_dir/toolchain-fixture/gcc-14.3.0/libstdc++-v3/escaped/version.date'
        link.parent.mkdir()
        link.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.collect()
        link.unlink()
        version_date = self.source/'build_dir/toolchain-fixture/gcc-14.3.0/libstdc++-v3/version.date'
        version_date.write_bytes(b'0' * (MODULE.VERSION_DATE_MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse(self.output.exists())

    def test_source_symlink_is_rejected_before_resolution(self):
        alias = self.root/'source-alias'
        alias.symlink_to(self.source, target_is_directory=True)
        with patch.dict(os.environ, {'SOURCE_DATE_EPOCH': '1782737960'}, clear=False):
            with self.assertRaises(ValueError):
                MODULE.collect(alias, self.output)
        self.assertFalse(self.output.exists())




if __name__ == '__main__':
    unittest.main()
