#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fingerprint four diagnostic ARM payloads without exporting their contents."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

PAYLOADS = ('usr/bin/iperf3', 'usr/lib/libiperf.so.0.0.0',
            'usr/lib/libelf-0.192.so', 'usr/lib/libstdc++.so.6.0.33')
LIMIT = 64 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def describe(data, prefix):
    if (not 52 <= len(data) <= LIMIT or data[:7] != b'\x7fELF\x01\x01\x01'
            or not prefix.startswith(b'/') or prefix == b'/' or b'\0' in prefix):
        raise ValueError('invalid ARM ELF or source prefix')
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    if header[2] != 40 or header[3] != 1 or header[8] != 52:
        raise ValueError('invalid ARM ELF header')
    phoff, stride, count = header[5], header[9], header[10]
    if (stride != 32 or not 1 <= count <= 256 or phoff < 52
            or phoff + stride * count > len(data)):
        raise ValueError('invalid program header table')
    result = {'size': len(data), 'sha256': digest(data),
              'header_sha256': digest(data[:52]), 'segments': [],
              'gnu_build_ids': [], 'source_path_strings': []}
    for index in range(count):
        kind, offset, vaddr, paddr, filesz, memsz, flags, align = struct.unpack_from(
            '<IIIIIIII', data, phoff + stride * index)
        if offset > len(data) or filesz > len(data) - offset:
            raise ValueError('segment outside file')
        payload = data[offset:offset + filesz]
        result['segments'].append(dict(index=index, type=kind, offset=offset,
            virtual_address=vaddr, physical_address=paddr, file_size=filesz,
            memory_size=memsz, flags=flags, alignment=align, sha256=digest(payload)))
        if kind == 4:  # PT_NOTE survives removal of the section table.
            cursor = 0
            while cursor < len(payload):
                if len(payload) - cursor < 12:
                    raise ValueError('truncated ELF note')
                namesz, descsz, note_type = struct.unpack_from('<III', payload, cursor)
                cursor += 12
                name_end = cursor + namesz
                desc_start = cursor + ((namesz + 3) & ~3)
                desc_end = desc_start + descsz
                next_note = desc_start + ((descsz + 3) & ~3)
                if name_end > len(payload) or next_note > len(payload):
                    raise ValueError('ELF note outside segment')
                if payload[cursor:name_end] == b'GNU\0' and note_type == 3:
                    if not 1 <= descsz <= 64:
                        raise ValueError('invalid GNU build ID size')
                    result['gnu_build_ids'].append(payload[desc_start:desc_end].hex())
                cursor = next_note
    needle = prefix.rstrip(b'/') + b'/'
    cursor = 0
    while True:
        start = data.find(needle, cursor)
        if start < 0:
            break
        end = data.find(b'\0', start, min(len(data), start + 4096))
        if end < 0 or len(result['source_path_strings']) >= 4096:
            raise ValueError('source path string exceeds diagnostic limits')
        value = data[start:end]
        normalized = b'<SOURCE_ROOT>/' + value[len(needle):]
        result['source_path_strings'].append({'offset': start, 'size': len(value),
            'sha256': digest(value), 'normalized_sha256': digest(normalized)})
        cursor = end + 1
    return result


def collect(root, source_root):
    root = root.resolve(strict=True)
    report = {'format': 1, 'source_root_sha256': digest(source_root.encode()),
              'payloads': {}}
    for name in PAYLOADS:
        path = root / name
        if (path.is_symlink() or not path.resolve(strict=True).is_relative_to(root)
                or not path.is_file() or path.stat().st_size > LIMIT):
            raise ValueError('unsafe diagnostic payload')
        with path.open('rb') as stream:
            report['payloads'][name] = describe(stream.read(LIMIT + 1), source_root.encode())
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs', type=Path, required=True)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = collect(args.rootfs, args.source_root)
    with args.output.open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write('\n')
