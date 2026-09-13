# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from repro_payload_evidence import PAYLOADS, collect, describe


def fixture(prefix=b'/build/a'):
    ident = b'\x7fELF\x01\x01\x01' + bytes(9)
    header = struct.pack('<16sHHIIIIIHHHHHH', ident, 3, 40, 1,
                         0, 52, 0, 0, 52, 32, 1, 0, 0, 0)
    note = struct.pack('<III', 4, 20, 3) + b'GNU\0' + bytes(range(20))
    ph = struct.pack('<IIIIIIII', 4, 84, 0, 0, len(note), len(note), 4, 4)
    return header + ph + note + prefix + b'/source.cc\0PRIVATE_CONTENT\0'


class PayloadEvidenceTests(unittest.TestCase):
    def test_note_and_normalized_path(self):
        a, b = describe(fixture(), b'/build/a'), describe(fixture(b'/other/root'), b'/other/root')
        self.assertEqual(a['gnu_build_ids'], [bytes(range(20)).hex()])
        self.assertNotEqual(a['sha256'], b['sha256'])
        self.assertEqual(a['source_path_strings'][0]['normalized_sha256'],
                         b['source_path_strings'][0]['normalized_sha256'])
        self.assertNotIn('PRIVATE_CONTENT', json.dumps(a))
        self.assertNotIn('source.cc', json.dumps(a))

    def test_wrong_architecture(self):
        data = bytearray(fixture()); struct.pack_into('<H', data, 18, 62)
        with self.assertRaises(ValueError): describe(bytes(data), b'/build/a')

    def test_bad_segment(self):
        data = bytearray(fixture()); struct.pack_into('<I', data, 56, 1000000)
        with self.assertRaises(ValueError): describe(bytes(data), b'/build/a')

    def test_bad_note(self):
        data = bytearray(fixture()); struct.pack_into('<I', data, 88, 1000000)
        with self.assertRaises(ValueError): describe(bytes(data), b'/build/a')

    def test_invalid_prefix_and_header(self):
        for data, prefix in [(b'ELF', b'/build'), (fixture(), b'/'), (fixture(), b'relative')]:
            with self.assertRaises(ValueError): describe(data, prefix)

    def test_collect_and_reject_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in PAYLOADS:
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(fixture())
            self.assertEqual(set(collect(root, '/build/a')['payloads']), set(PAYLOADS))
            path.unlink(); path.symlink_to('/etc/passwd')
            with self.assertRaises(ValueError): collect(root, '/build/a')
