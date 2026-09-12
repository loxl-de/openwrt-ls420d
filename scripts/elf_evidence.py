#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fingerprint ELF32 ARM sections without exporting names or payloads."""
import hashlib
import struct


def elf_evidence(data):
    if not data.startswith(b'\x7fELF'):
        return None
    if len(data) > 64 * 1024 * 1024 or len(data) < 52:
        raise ValueError('invalid ELF size')
    if data[4:7] != b'\x01\x01\x01':
        raise ValueError('expected ELF32 little-endian version 1')
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    if header[2] != 40 or header[3] != 1 or header[8] != 52:
        raise ValueError('expected ARM ELF header')
    offset, stride, count = header[6], header[11], header[12]
    if offset == 0 and count == 0:
        # sstrip removes the section table. Preserve every file byte in
        # bounded block fingerprints; do not reconstruct stripped padding.
        return {'format': 1, 'sections': [], 'block_size': 4096,
                'header_sha256': hashlib.sha256(data[:52]).hexdigest(),
                'blocks': [hashlib.sha256(data[pos:pos + 4096]).hexdigest()
                           for pos in range(0, len(data), 4096)]}
    if stride != 40 or not 1 <= count <= 4096:
        raise ValueError('unsupported ELF section table')
    if offset < 52 or offset + count * stride > len(data):
        raise ValueError('ELF section table outside file')
    sections = []
    for index in range(count):
        values = struct.unpack_from('<IIIIIIIIII', data, offset + index * stride)
        name, kind, flags, address, start, size, link, info, alignment, entsize = values
        item = dict(index=index, type=kind, flags=flags, address=address,
                    offset=start, size=size, link=link, info=info,
                    alignment=alignment, entry_size=entsize, name_offset=name)
        if kind not in (0, 8):  # NULL and NOBITS have no file payload.
            if start > len(data) or size > len(data) - start:
                raise ValueError('ELF section outside file')
            item['sha256'] = hashlib.sha256(data[start:start + size]).hexdigest()
        sections.append(item)
    return {'format': 1, 'header_sha256': hashlib.sha256(data[:52]).hexdigest(),
            'sections': sections}
