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

Two extents are taken from the PT_LOAD segments of vmlinux. The image
extent (file-backed bytes) is what the decompressor writes and what it keeps
clear when relocating itself; the footprint (memory size, including .bss) is
what the kernel reserves at boot, and an initrd inside that reservation is
disabled rather than overwritten. Both must stay below the initrd load
address. The margin covers the relocated zImage plus decompressor scratch.
"""
import struct
import sys
from pathlib import Path

KERNEL_PHYS = 0x00008000
INITRD_LOAD = 0x02600000
DECOMPRESSOR_SCRATCH = 1024 * 1024


def load_footprint(vmlinux):
    """Return (lowest, highest memory end, highest file-backed end) of PT_LOAD."""
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
    lowest = highest = highest_file = None
    for index in range(e_phnum):
        offset = e_phoff + index * e_phentsize
        entry = vmlinux[offset:offset + 32]
        if len(entry) != 32:
            raise ValueError('truncated program header table')
        p_type, _, _, p_paddr, p_filesz, p_memsz, _, _ = struct.unpack(order + '8I', entry)
        if p_type != 1 or p_memsz == 0:
            continue
        lowest = p_paddr if lowest is None else min(lowest, p_paddr)
        highest = p_paddr + p_memsz if highest is None else max(highest, p_paddr + p_memsz)
        highest_file = p_paddr + p_filesz if highest_file is None else max(highest_file, p_paddr + p_filesz)
    if lowest is None:
        raise ValueError('vmlinux has no PT_LOAD segment')
    return lowest, highest, highest_file


def check(vmlinux, uimage_size):
    """Return (image, footprint, decompressor_end, worst_case_end) in bytes."""
    lowest, highest, highest_file = load_footprint(vmlinux)
    image = highest_file - lowest
    footprint = highest - lowest
    decompressor_end = KERNEL_PHYS + image + uimage_size + DECOMPRESSOR_SCRATCH
    worst_case_end = KERNEL_PHYS + max(footprint, image + uimage_size + DECOMPRESSOR_SCRATCH)
    return image, footprint, decompressor_end, worst_case_end


def report(image, footprint, uimage_size, decompressor_end, end):
    """KEY=VALUE lines for the build manifest; the numbers behind the verdict."""
    return (f'KERNEL_LOAD_ADDRESS=0x{KERNEL_PHYS:08x}\n'
            f'KERNEL_IMAGE_BYTES={image}\n'
            f'KERNEL_FOOTPRINT_BYTES={footprint}\n'
            f'UIMAGE_BYTES={uimage_size}\n'
            f'DECOMPRESSOR_SCRATCH_BYTES={DECOMPRESSOR_SCRATCH}\n'
            f'DECOMPRESSOR_END=0x{decompressor_end:08x}\n'
            f'KERNEL_WORST_CASE_END=0x{end:08x}\n'
            f'INITRD_LOAD_ADDRESS=0x{INITRD_LOAD:08x}\n'
            f'INITRD_HEADROOM_BYTES={INITRD_LOAD - end}\n')


def main(argv):
    if len(argv) != 3:
        raise SystemExit('usage: check-kernel-footprint.py VMLINUX UIMAGE')
    vmlinux_path, uimage_path = map(Path, argv[1:])
    uimage_size = uimage_path.stat().st_size
    image, footprint, decompressor_end, end = check(vmlinux_path.read_bytes(), uimage_size)
    text = report(image, footprint, uimage_size, decompressor_end, end)
    print(text, end='')
    sys.stdout.flush()
    if decompressor_end >= INITRD_LOAD:
        verdict = 'the zImage decompressor would overwrite the Buffalo initrd'
    elif end >= INITRD_LOAD:
        verdict = 'the kernel reservation (.bss) would cover the initrd and Linux would disable it'
    else:
        return
    # Repeat the numbers on stderr: a failing step must show them in the log
    # even when stdout was redirected into the evidence file.
    raise SystemExit(verdict + '; shrink the package set or compress the embedded initramfs\n' + text)


if __name__ == '__main__':
    main(sys.argv)
