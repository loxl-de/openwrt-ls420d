# SPDX-License-Identifier: MIT
import hashlib
import json
import shutil
import subprocess
import tempfile
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from elf_evidence import elf_evidence


def fixture(kind=1, size=4):
    ident = b'\x7fELF\x01\x01\x01' + bytes(9)
    header = struct.pack('<16sHHIIIIIHHHHHH', ident, 3, 40, 1,
                         0, 0, 52, 0, 52, 0, 0, 40, 1, 0)
    section = struct.pack('<IIIIIIIIII', 0, kind, 2, 0, 92, size, 0, 0, 4, 0)
    return header + section + b'test'


class ElfEvidenceTests(unittest.TestCase):
    def test_non_elf(self):
        self.assertIsNone(elf_evidence(b'plain text'))

    def test_payload_fingerprint(self):
        result = elf_evidence(fixture())
        self.assertEqual(result['sections'][0]['size'], 4)
        self.assertNotIn('test', str(result))
        self.assertNotEqual(result, elf_evidence(fixture()[:-1] + b'x'))

    def test_nobits(self):
        self.assertNotIn('sha256', elf_evidence(fixture(8, 1000000))['sections'][0])

    def test_truncated_header(self):
        with self.assertRaises(ValueError):
            elf_evidence(b'\x7fELF')

    def test_truncated_table(self):
        with self.assertRaises(ValueError):
            elf_evidence(fixture()[:80])

    def test_bad_payload_range(self):
        with self.assertRaises(ValueError):
            elf_evidence(fixture(size=5))

    def test_wrong_architecture(self):
        data = bytearray(fixture())
        struct.pack_into('<H', data, 18, 62)
        with self.assertRaises(ValueError):
            elf_evidence(bytes(data))

    def test_rootfs_audit_integration(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'root'
            shutil.copytree(repo / 'openwrt/files', root)
            sample = root / 'etc/elf-fixture'
            sample.write_bytes(fixture())
            report = Path(directory) / 'inventory.json'
            subprocess.run([sys.executable, str(repo / 'scripts/audit-rootfs.py'),
                            str(root), str(report)], check=True, capture_output=True)
            entry = json.loads(report.read_text())['etc/elf-fixture']
            self.assertEqual(entry['sha256'], hashlib.sha256(fixture()).hexdigest())
            self.assertEqual(entry['elf_details'], elf_evidence(fixture()))
            sample.write_bytes(b'\x7fELF')
            result = subprocess.run([sys.executable, str(repo / 'scripts/audit-rootfs.py'),
                                     str(root), str(report)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
