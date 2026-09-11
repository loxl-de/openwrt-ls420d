#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('kernel_config', REPO/'scripts/compare-kernel-config.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def config(root='/original/openwrt', architecture='arm_cortex-a9+vfpv3-d16_musl_eabi'):
    return ('CONFIG_BTRFS_FS=y\n'
            f'CONFIG_INITRAMFS_SOURCE="{root}/build_dir/target-{architecture}/root-mvebu '
            f'{root}/target/linux/generic/image/initramfs-base-files.txt"\n'
            'CONFIG_INITRAMFS_ROOT_UID=1001\n')


class KernelConfigTests(unittest.TestCase):
    def test_only_checkout_root_may_change(self):
        MODULE.compare(config(), config('/offline/openwrt'), Path('/offline/openwrt'))

    def test_kernel_option_difference_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.compare(config(), config('/offline/openwrt').replace('BTRFS_FS=y', 'BTRFS_FS=m'),
                           Path('/offline/openwrt'))

    def test_root_owner_difference_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.compare(config(), config('/offline/openwrt').replace('ROOT_UID=1001', 'ROOT_UID=0'),
                           Path('/offline/openwrt'))

    def test_architecture_change_is_not_normalized(self):
        with self.assertRaises(ValueError):
            MODULE.compare(config(), config('/offline/openwrt', 'different'), Path('/offline/openwrt'))

    def test_unexpected_checkout_or_extra_input_is_rejected(self):
        for actual in [config('/elsewhere/openwrt'),
                       config('/offline/openwrt').replace('root-mvebu ', 'root-mvebu /extra ')]:
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                MODULE.compare(config(), actual, Path('/offline/openwrt'))

    def test_mixed_roots_and_traversal_are_rejected(self):
        for actual in [config('/offline/openwrt').replace('/offline/openwrt/build_dir', '/other/build_dir'),
                       config('/offline/../openwrt')]:
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                MODULE.compare(config(), actual, Path('/offline/openwrt'))

    def test_missing_or_duplicate_setting_is_rejected(self):
        for actual in ['CONFIG_BTRFS_FS=y\n', config()+config()]:
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                MODULE.compare(config(), actual, Path('/original/openwrt'))


    def test_report_keeps_compiler_version_difference(self):
        report = MODULE.comparison_report(
            config()+'CONFIG_RUSTC_VERSION=109801\n',
            config('/offline/openwrt')+'CONFIG_RUSTC_VERSION=109900\n',
            Path('/offline/openwrt'))
        self.assertTrue(report['valid_inputs'])
        self.assertFalse(report['match'])
        self.assertIn('-CONFIG_RUSTC_VERSION=109801', report['differences'])
        self.assertIn('+CONFIG_RUSTC_VERSION=109900', report['differences'])

    def test_report_rebases_only_paths_and_records_original_hashes(self):
        report = MODULE.comparison_report(config(), config('/offline/openwrt'),
                                          Path('/offline/openwrt'))
        self.assertTrue(report['match'])
        self.assertEqual(report['differences'], [])
        self.assertNotEqual(report['expected_sha256'], report['actual_sha256'])

    def test_cli_saves_mismatch_and_invalid_input_reports(self):
        cases = [(config('/offline/openwrt').replace('BTRFS_FS=y', 'BTRFS_FS=m'), 1, True),
                 (config('/wrong/openwrt'), 2, False)]
        for actual, status, valid in cases:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/'expected').write_text(config())
                (root/'actual').write_text(actual)
                process = subprocess.run(
                    ['python3', str(REPO/'scripts/compare-kernel-config.py'),
                     str(root/'expected'), str(root/'actual'), '--source-root', '/offline/openwrt',
                     '--report', str(root/'report.json')], capture_output=True, text=True)
                self.assertEqual(process.returncode, status)
                report = json.loads((root/'report.json').read_text())
                self.assertEqual(report['valid_inputs'], valid)
                self.assertFalse(report['match'])


if __name__ == '__main__':
    unittest.main()
