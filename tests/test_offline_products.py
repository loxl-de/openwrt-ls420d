#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('offline_products', REPO/'scripts/report-offline-products.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OfflineProductTests(unittest.TestCase):
    def run_report(self, config, changed_product=False):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work/'bundle').mkdir()
            (work/'artifacts').mkdir()
            manifest = ['REPOSITORY_COMMIT='+'1'*40]
            for name in MODULE.PRODUCTS:
                data = name.encode()
                (work/'artifacts'/name).write_bytes(data)
                manifest.append(f'ARTIFACT_SHA256[{name}]={hashlib.sha256(data).hexdigest()}')
            if changed_product:
                (work/'artifacts/uImage.buffalo').write_bytes(b'different')
            (work/'bundle/build.manifest').write_text('\n'.join(manifest)+'\n')
            (work/'RESTORED.json').write_text(json.dumps({'source_zip_sha256': '2'*64}))
            (work/'offline-config-result.json').write_text(json.dumps(config))
            process = subprocess.run(
                ['python3', str(REPO/'scripts/report-offline-products.py'), str(work)],
                capture_output=True, text=True)
            report = json.loads((work/'offline-result.json').read_text())
            return process, report

    def test_matching_products_and_config_pass(self):
        process, report = self.run_report({'valid_inputs': True, 'match': True})
        self.assertEqual(process.returncode, 0)
        self.assertTrue(report['all_checks_passed'])
        self.assertFalse(report['firmware_distribution_authorized'])
        self.assertFalse(report['license_review_complete'])

    def test_matching_products_cannot_hide_config_mismatch(self):
        process, report = self.run_report({'valid_inputs': True, 'match': False})
        self.assertNotEqual(process.returncode, 0)
        self.assertTrue(report['all_products_match'])
        self.assertFalse(report['all_checks_passed'])
        self.assertFalse(report['kernel_config_match'])

    def test_product_mismatch_is_recorded_and_fails(self):
        process, report = self.run_report({'valid_inputs': True, 'match': True}, True)
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse(report['all_products_match'])
        self.assertFalse(report['products']['uImage.buffalo']['match'])
        self.assertTrue(report['products']['initrd.buffalo']['match'])

    def test_missing_invalid_and_nonboolean_config_results_cannot_pass(self):
        for config in ({}, {'valid_inputs': False, 'match': True},
                       {'valid_inputs': 'true', 'match': 'true'}):
            with self.subTest(config=config):
                process, report = self.run_report(config)
                self.assertNotEqual(process.returncode, 0)
                self.assertFalse(report['all_checks_passed'])


if __name__ == '__main__':
    unittest.main()
