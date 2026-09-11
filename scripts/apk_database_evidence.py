# SPDX-License-Identifier: MIT
"""Fingerprint APK database fields and script members without exporting contents."""
import gzip
import hashlib
import io
from pathlib import Path
import re
import tarfile

LIMIT = 8 * 1024 * 1024
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9+_.-]{0,255}')
SCRIPT_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9+_.~-]{0,255}')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_input(root, relative):
    path = root / relative
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlinked APK database input')
    if not path.is_file() or path.stat().st_size > LIMIT:
        raise ValueError('missing or oversized APK database input')
    return path.read_bytes()


def installed_evidence(data):
    if len(data) > LIMIT or not data.endswith(b'\n\n'):
        raise ValueError('invalid installed database framing')
    packages = {}
    order = []
    for record in data[:-2].split(b'\n\n'):
        fields = {}
        lines = record.split(b'\n')
        for line in lines:
            if len(line) < 2 or line[1:2] != b':' or not chr(line[0]).isascii() or not chr(line[0]).isalpha():
                raise ValueError('invalid installed database field')
            key = chr(line[0])
            fields.setdefault(key, []).append(digest(line[2:]))
        names = [line[2:] for line in lines if line.startswith(b'P:')]
        if len(names) != 1:
            raise ValueError('missing or duplicate package name')
        name = names[0].decode('ascii')
        if not NAME.fullmatch(name) or name in packages:
            raise ValueError('invalid or duplicate package name')
        packages[name] = {
            'record_sha256': digest(record),
            'sorted_lines_sha256': digest(b'\n'.join(sorted(lines))),
            'fields': fields,
        }
        order.append(name)
        if len(packages) > 4096:
            raise ValueError('too many installed packages')
    return {'packages': packages, 'order_sha256': digest('\n'.join(order).encode())}


def scripts_evidence(data):
    if len(data) > LIMIT:
        raise ValueError('oversized script archive')
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
        raw = compressed.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('oversized expanded script archive')
    members = {}
    order = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            if (not member.isfile() or member.pax_headers or
                    not SCRIPT_NAME.fullmatch(member.name) or member.name in members or
                    member.size > LIMIT or len(members) >= 4096):
                raise ValueError('unsupported or duplicate script member')
            with archive.extractfile(member) as stream:
                content = stream.read(LIMIT + 1)
            if len(content) != member.size:
                raise ValueError('truncated script member')
            members[member.name] = {
                'sha256': digest(content), 'size': member.size,
                'mode': member.mode, 'mtime': member.mtime,
                'uid': member.uid, 'gid': member.gid,
                'uname_sha256': digest(member.uname.encode()),
                'gname_sha256': digest(member.gname.encode()),
            }
            order.append(member.name)
    return {
        'members': members,
        'order_sha256': digest('\n'.join(order).encode()),
        'uncompressed_sha256': digest(raw),
        'gzip_header_hex': data[:10].hex(),
    }


def database_evidence(root):
    root = Path(root)
    return {
        'lib/apk/db/installed': installed_evidence(read_input(root, 'lib/apk/db/installed')),
        'lib/apk/db/scripts.tar.gz': scripts_evidence(read_input(root, 'lib/apk/db/scripts.tar.gz')),
    }
