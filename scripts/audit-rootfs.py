#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit built-in defaults and fingerprint rootfs contents without exporting them."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

from apk_database_evidence import database_evidence
from elf_evidence import elf_evidence

root, output = map(Path, sys.argv[1:])
for name in ('etc', 'etc/config'):
    if (root/name).is_symlink() or not (root/name).is_dir():
        raise SystemExit('unsafe generic rootfs configuration parent')
public = Path(__file__).resolve().parents[1]/'openwrt/files'
for name in ('dropbear', 'network', 'dhcp', 'firewall'):
    path = root/'etc/config'/name
    if path.is_symlink() or path.read_bytes() != (public/'etc/config'/name).read_bytes():
        raise SystemExit('generic rootfs defaults differ from the reviewed public overlay')
for name in ('etc/dropbear', 'root/.ssh'):
    path = root/name
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise SystemExit('unsafe generic rootfs key directory')
    if path.exists() and any(path.iterdir()):
        raise SystemExit('generic rootfs contains SSH key or authorization files')
inventory = {}
for path in sorted(root.rglob('*')):
    mode = path.lstat().st_mode
    kind = 'symlink' if stat.S_ISLNK(mode) else 'directory' if stat.S_ISDIR(mode) else 'file' if stat.S_ISREG(mode) else 'special'
    entry = {'type': kind, 'mode': stat.S_IMODE(mode)}
    if kind == 'file':
        checksum = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                checksum.update(chunk)
        entry['sha256'] = checksum.hexdigest()
        entry['size'] = path.stat().st_size
        with path.open('rb') as stream:
            if stream.read(4) == b'\x7fELF':
                if entry['size'] > 64 * 1024 * 1024:
                    raise SystemExit('ELF exceeds diagnostic size limit')
                stream.seek(0)
                entry['elf_details'] = elf_evidence(stream.read(64 * 1024 * 1024 + 1))
    elif kind == 'symlink':
        entry['target'] = os.readlink(path)
    inventory[path.relative_to(root).as_posix()] = entry
if (root/'lib/apk/db').exists() or (root/'lib/apk/db').is_symlink():
    for name, details in database_evidence(root).items():
        inventory[name]['apk_details'] = details
output.write_text(json.dumps(inventory, sort_keys=True, indent=2)+'\n')
