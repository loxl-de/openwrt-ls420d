#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('license_review', REPO/'scripts/review-package-licenses.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LicenseReviewTests(unittest.TestCase):
    def test_abi_suffix_and_recipe_scope(self):
        text = ('Source-Makefile: package/libs/example/Makefile\n'
                'Package: libexample\nABI-Version: 1\nLicense: MIT\n'
                'LicenseFiles: COPYING LICENSE\nDescription: text\n@@\n'
                'Package: libusb-1.0\nABI-Version: 0\nLicense: LGPL-2.1-or-later\n')
        report = MODULE.review('libexample1 - 2-r1\nlibusb-1.0-0 - 3-r1\n', text)
        self.assertEqual(report['package_count'], 2)
        self.assertEqual(report['packages'][0]['declared_license_files'], ['COPYING', 'LICENSE'])
        self.assertEqual(report['packages'][1]['recipe'], 'package/libs/example/Makefile')
        self.assertFalse(report['license_review_complete'])
        self.assertFalse(report['firmware_distribution_authorized'])

    def test_description_cannot_supply_license_fields(self):
        text = 'Package: example\nDescription: text\nLicense: invented\n@@\n'
        report = MODULE.review('example - 1\n', text)
        self.assertEqual(report['packages'][0]['finding'], 'missing license declaration')

    def test_missing_and_ambiguous_metadata_are_findings(self):
        text = 'Package: a\nLicense: MIT\nPackage: a\nLicense: BSD-3-Clause\n'
        report = MODULE.review('a - 1\nkernel - 6.12\n', text)
        self.assertEqual([p['finding'] for p in report['packages']],
                         ['ambiguous metadata', 'missing metadata'])

    def test_duplicate_manifest_package_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.review('a - 1\na - 2\n', '')


if __name__ == '__main__':
    unittest.main()
