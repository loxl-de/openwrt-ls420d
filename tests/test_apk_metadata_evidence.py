# SPDX-License-Identifier: MIT
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'apk_metadata_evidence', Path(__file__).resolve().parents[1] /
    'scripts/apk_metadata_evidence.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MetadataEvidenceTests(unittest.TestCase):
    def test_no_raw_keys_or_values(self):
        result = json.dumps(module.fingerprint({'private/path': ['secret body', 12345]}))
        for forbidden in ('private/path', 'secret body', '12345'):
            self.assertNotIn(forbidden, result)

    def test_order_and_types_are_preserved(self):
        self.assertNotEqual(module.fingerprint([1, 2]), module.fingerprint([2, 1]))
        self.assertNotEqual(module.fingerprint(1), module.fingerprint('1'))
        self.assertNotEqual(module.fingerprint(None), module.fingerprint(False))

    def test_object_order_is_irrelevant(self):
        self.assertEqual(module.fingerprint({'a': 1, 'b': 2}),
                         module.fingerprint({'b': 2, 'a': 1}))

    def test_changed_value_is_visible(self):
        self.assertNotEqual(module.fingerprint({'mtime': 1}),
                            module.fingerprint({'mtime': 2}))

    def cli(self, raw):
        import subprocess
        import sys
        return subprocess.run([sys.executable, str(spec.origin)], input=raw,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=10)

    def test_cli_accepts_valid_data(self):
        result = self.cli(b'{"file": {"mtime": 123}}')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['schema'], 1)
        self.assertNotIn(b'mtime', result.stdout)

    def test_cli_rejects_bad_json_without_echoing_input(self):
        for raw in (b'private-invalid', b'{"secret":1,"secret":2}',
                    b'NaN', b'Infinity', b'1e999', b'[' * 2000,
                    b'{"\\ud800":1}', b'\xff'):
            with self.subTest(raw=raw[:30]):
                result = self.cli(raw)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b'')
                self.assertNotIn(b'Traceback', result.stderr)
                self.assertNotIn(b'secret', result.stderr)

    def test_cli_rejects_oversize_input(self):
        result = self.cli(b' ' * (16 * 1024 * 1024 + 1))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')
