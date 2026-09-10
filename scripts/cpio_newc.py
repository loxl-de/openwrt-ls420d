#!/usr/bin/env python3
"""Small deterministic newc codec. No extraction or shell execution."""
import dataclasses
import stat
import struct
import zlib


@dataclasses.dataclass(frozen=True)
class Entry:
    name: str
    mode: int
    data: bytes = b''
    uid: int = 0
    gid: int = 0
    rmajor: int = 0
    rminor: int = 0


def safe_name(name):
    if name == '.':
        return name
    name = name.removeprefix('./')
    if not name or name.startswith('/') or '\\' in name or any(
            c in name for c in '\r\n\0') or any(p in ('', '.', '..') for p in name.split('/')):
        raise ValueError('unsafe archive path')
    return name


def encode(entries):
    result = bytearray()
    seen = set()
    for ino, entry in enumerate([*entries, Entry('TRAILER!!!', 0)], 1):
        name = safe_name(entry.name)
        if name in seen:
            raise ValueError('duplicate archive path')
        seen.add(name)
        encoded = name.encode() + b'\0'
        values = [ino, entry.mode, entry.uid, entry.gid, 1, 0, len(entry.data),
                  0, 0, entry.rmajor, entry.rminor, len(encoded), 0]
        result.extend(b'070701' + ''.join(f'{n:08x}' for n in values).encode())
        result.extend(encoded)
        result.extend(bytes(-len(result) % 4))
        result.extend(entry.data)
        result.extend(bytes(-len(result) % 4))
    result.extend(bytes(-len(result) % 512))
    return bytes(result)


def decode(data, start=0):
    """Read one archive; return entries and end, excluding optional zero padding."""
    entries, seen, pos = [], set(), start
    while True:
        header = data[pos:pos + 110]
        if len(header) != 110 or header[:6] != b'070701':
            raise ValueError('invalid newc header')
        fields = [int(header[6 + n * 8:14 + n * 8], 16) for n in range(13)]
        _, mode, uid, gid, nlink, _, size, _, _, rmajor, rminor, namesize, check = fields
        if not 1 <= namesize <= 4096 or check or nlink > 2**20:
            raise ValueError('invalid newc metadata')
        pos += 110
        rawname = data[pos:pos + namesize]
        if len(rawname) != namesize or rawname[-1:] != b'\0' or b'\0' in rawname[:-1]:
            raise ValueError('invalid newc name')
        name = safe_name(rawname[:-1].decode())
        pos += namesize
        pos += -(pos - start) % 4
        payload = data[pos:pos + size]
        if len(payload) != size:
            raise ValueError('truncated newc data')
        pos += size
        pos += -(pos - start) % 4
        if name == 'TRAILER!!!':
            if size:
                raise ValueError('invalid trailer')
            return entries, pos
        if name in seen:
            raise ValueError('duplicate archive path')
        seen.add(name)
        entries.append(Entry(name, mode, payload, uid, gid, rmajor, rminor))


def wrap_ramdisk(payload):
    # uImage: magic, header CRC, deterministic time, size, load, entry, data CRC;
    # OS Linux, architecture ARM, type RAMDisk, compression none.
    fields = [0x27051956, 0, 0, len(payload), 0, 0, zlib.crc32(payload), 5, 2, 3, 0,
              b'LS420D deployment CPIO'.ljust(32, b'\0')]
    header = struct.pack('>7I4B32s', *fields)
    fields[1] = zlib.crc32(header)
    return struct.pack('>7I4B32s', *fields) + payload


def unwrap_ramdisk(blob):
    if len(blob) < 64:
        raise ValueError('short ramdisk')
    f = struct.unpack('>7I4B32s', blob[:64])
    if f[0] != 0x27051956 or f[7:11] != (5, 2, 3, 0) or len(blob) != 64 + f[3]:
        raise ValueError('wrong ramdisk format')
    if f[1] != zlib.crc32(blob[:4] + bytes(4) + blob[8:64]) or f[6] != zlib.crc32(blob[64:]):
        raise ValueError('ramdisk CRC mismatch')
    return blob[64:]
