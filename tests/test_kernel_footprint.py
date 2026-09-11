#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the footprint check against synthetic ARM ELF images."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('footprint', REPO/'scripts/check-kernel-footprint.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def elf(segments, machine=40, elf_class=1):
    """Build a minimal ELF32 with PT_LOAD entries of (paddr, filesz, memsz)."""
    phnum = len(segments)
    header = b'\x7fELF' + bytes([elf_class, 1, 1, 0]) + bytes(8)
    header += struct.pack('<HHIIIIIHHHHHH', 2, machine, 1, 0x8000, 52, 0, 0, 52, 32, phnum, 0, 0, 0)
    table = b''
    for paddr, filesz, memsz in segments:
        table += struct.pack('<8I', 1, 0, paddr, paddr, filesz, memsz, 6, 4)
    return header + table


class FootprintTests(unittest.TestCase):
    def test_bss_counts_toward_footprint(self):
        image = elf([(0x8000, 0x100000, 0x100000), (0x108000, 0x1000, 0x300000)])
        self.assertEqual(MODULE.load_footprint(image), (0x8000, 0x408000))

    def test_small_kernel_passes(self):
        footprint, end = MODULE.check(elf([(0x8000, 0x800000, 0x800000)]), 5 * 1024 * 1024)
        self.assertEqual(footprint, 0x800000)
        self.assertLess(end, MODULE.INITRD_LOAD)

    def test_uncompressed_initramfs_near_limit_fails(self):
        # 36 MiB decompressed plus a 3 MiB uImage plus scratch crosses 38 MiB.
        big = elf([(0x8000, 36 * 1024 * 1024, 36 * 1024 * 1024)])
        _, end = MODULE.check(big, 3 * 1024 * 1024)
        self.assertGreaterEqual(end, MODULE.INITRD_LOAD)

    def test_rejects_non_arm_or_64bit(self):
        with self.assertRaises(ValueError):
            MODULE.load_footprint(elf([(0x8000, 16, 16)], machine=3))
        with self.assertRaises(ValueError):
            MODULE.load_footprint(elf([(0x8000, 16, 16)], elf_class=2))
        with self.assertRaises(ValueError):
            MODULE.load_footprint(b'not an elf')

    def test_cli_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            vmlinux = Path(tmp)/'vmlinux'
            uimage = Path(tmp)/'uImage.buffalo'
            uimage.write_bytes(bytes(4096))
            vmlinux.write_bytes(elf([(0x8000, 40 * 1024 * 1024, 40 * 1024 * 1024)]))
            result = subprocess.run([sys.executable, str(REPO/'scripts/check-kernel-footprint.py'),
                                     str(vmlinux), str(uimage)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('initrd load address', result.stderr)
            vmlinux.write_bytes(elf([(0x8000, 8 * 1024 * 1024, 8 * 1024 * 1024)]))
            result = subprocess.run([sys.executable, str(REPO/'scripts/check-kernel-footprint.py'),
                                     str(vmlinux), str(uimage)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            values = dict(line.split('=', 1) for line in result.stdout.splitlines())
            self.assertEqual(values['KERNEL_FOOTPRINT_BYTES'], str(8 * 1024 * 1024))
            self.assertEqual(values['INITRD_LOAD_ADDRESS'], '0x02600000')
            self.assertEqual(int(values['KERNEL_WORST_CASE_END'], 16) + int(values['INITRD_HEADROOM_BYTES']),
                             MODULE.INITRD_LOAD)


if __name__ == '__main__':
    unittest.main()
