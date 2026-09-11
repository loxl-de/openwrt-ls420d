#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import importlib.util
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


if __name__ == '__main__':
    unittest.main()
