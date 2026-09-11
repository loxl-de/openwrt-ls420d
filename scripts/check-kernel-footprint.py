#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check that the decompressed kernel cannot overlap the external initrd.

Buffalo's U-Boot loads uImage.buffalo at 0x01200000 and initrd.buffalo at
0x02600000. The zImage decompressor places the uncompressed kernel at the
platform text offset 0x00008000 and, when the zImage itself lies inside that
destination range, first relocates itself directly behind the decompressed
image. With an embedded initramfs the decompressed image is roughly as large
as the whole root filesystem. If it reaches the initrd load address, the
decompressor or the kernel overwrites the companion before Linux can even
detect the overlap. The compressed uImage size does not reveal this.

The footprint is taken from the PT_LOAD segments of vmlinux, which include
.bss. The margin covers the relocated zImage plus decompressor scratch space.
"""
import struct
import sys
from pathlib import Path

KERNEL_PHYS = 0x00008000
INITRD_LOAD = 0x02600000
DECOMPRESSOR_SCRATCH = 1024 * 1024


def load_footprint(vmlinux):
    """Return (lowest, highest) physical address covered by PT_LOAD segments."""
    header = vmlinux[:52]
    if len(header) != 52 or header[:4] != b'\x7fELF' or header[4] != 1:
        raise ValueError('vmlinux is not a 32-bit ELF file')
    little = header[5] == 1
    if header[5] not in (1, 2):
        raise ValueError('vmlinux has an invalid ELF data encoding')
    order = '<' if little else '>'
    e_type, e_machine = struct.unpack(order + 'HH', header[16:20])
    if e_type != 2 or e_machine != 40:
        raise ValueError('vmlinux is not an executable ARM ELF file')
    e_phoff, = struct.unpack(order + 'I', header[28:32])
    e_phentsize, e_phnum = struct.unpack(order + 'HH', header[42:46])
    if e_phentsize != 32 or e_phnum == 0:
        raise ValueError('vmlinux has no usable program headers')
    lowest = highest = None
    for index in range(e_phnum):
        offset = e_phoff + index * e_phentsize
        entry = vmlinux[offset:offset + 32]
        if len(entry) != 32:
            raise ValueError('truncated program header table')
        p_type, _, _, p_paddr, _, p_memsz, _, _ = struct.unpack(order + '8I', entry)
        if p_type != 1 or p_memsz == 0:
            continue
        lowest = p_paddr if lowest is None else min(lowest, p_paddr)
        highest = p_paddr + p_memsz if highest is None else max(highest, p_paddr + p_memsz)
    if lowest is None:
        raise ValueError('vmlinux has no PT_LOAD segment')
    return lowest, highest


def check(vmlinux, uimage_size):
    lowest, highest = load_footprint(vmlinux)
    footprint = highest - lowest
    end = KERNEL_PHYS + footprint + uimage_size + DECOMPRESSOR_SCRATCH
    return footprint, end


def main(argv):
    if len(argv) != 3:
        raise SystemExit('usage: check-kernel-footprint.py VMLINUX UIMAGE')
    vmlinux_path, uimage_path = map(Path, argv[1:])
    uimage_size = uimage_path.stat().st_size
    footprint, end = check(vmlinux_path.read_bytes(), uimage_size)
    print(f'kernel footprint {footprint} bytes, worst-case end 0x{end:08x}, '
          f'initrd load address 0x{INITRD_LOAD:08x}')
    if end >= INITRD_LOAD:
        raise SystemExit('decompressed kernel would reach the Buffalo initrd load address; '
                         'shrink the package set or compress the embedded initramfs')


if __name__ == '__main__':
    main(sys.argv)
