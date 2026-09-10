#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit built-in rootfs defaults and write a deterministic path/type inventory."""
import json
from pathlib import Path
import stat
import sys

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
    inventory[path.relative_to(root).as_posix()] = {'type': kind}
output.write_text(json.dumps(inventory, sort_keys=True, indent=2)+'\n')
