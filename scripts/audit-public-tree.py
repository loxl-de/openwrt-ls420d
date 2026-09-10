#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail closed on tracked public-source hazards; never print matching values."""
import argparse
import fnmatch
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

MAX_BYTES = 16 * 1024 * 1024
PATTERNS = {
    'private-key': re.compile(rb'BEGIN (?:OPENSSH|RSA|EC|DSA|ENCRYPTED|PGP)? ?PRIVATE KEY'),
    'ssh-authorization': re.compile(rb'(?:ssh-(?:rsa|ed25519)|ecdsa-sha2-nistp[0-9]+) [A-Za-z0-9+/]{24,}'),
    'access-token': re.compile(rb'github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}'),
    'device-identifier': re.compile(rb'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}'),
    'personal-path': re.compile(rb'/mnt/[a-z]/[Uu]sers/|/home/[A-Za-z0-9._-]+/|[A-Za-z]:[/\\]Users[/\\]', re.I),
    'conversation-link': re.compile(rb'chatgpt\.com/(?:c/|share/|codex/(?:task|tasks)/)|codex:' + rb'//', re.I),
}
FORBIDDEN = (
    '*.db', '*.sqlite*', '*.img', '*.bin', '*.itb', '*.ubi', '*.ubifs',
    '*.squashfs', '*.cpio', '*.tar*', '*.zip', '*.gz', '*.xz', '*.pcap*',
    '*.dump', '*.key', '*.pem', '*.pub', '.env', '.env.*', 'known_hosts*',
    'authorized_keys*', 'id_rsa*', 'id_ed25519*', 'id_ecdsa*', 'id_dsa*',
    'ssh_host_*', 'dropbear_*_host_key*', '*u-boot*dump*', '*fw_env*dump*',
    'uimage.buffalo', 'initrd.buffalo', 'inventory-manifest*',
)


def forbidden_path(name):
    parts = PurePosixPath(name).parts
    return any(p.lower() in ('private', '.ssh') for p in parts) or any(
        fnmatch.fnmatchcase(p.lower(), pattern) for p in parts for pattern in FORBIDDEN
    )


def findings(data):
    if b'\0' in data:
        return [(0, 'binary-source')]
    return [(line_no, kind) for line_no, line in enumerate(data.splitlines(), 1)
            for kind, pattern in PATTERNS.items() if pattern.search(line)]


def audit(root):
    # Git paths are untrusted too: do not print them. An entry ordinal is enough
    # to find the offending item locally with git ls-files (NUL-delimited order).
    result = subprocess.run(['git', '-C', str(root), 'ls-files', '--stage', '-z'],
                            capture_output=True, check=True)
    failed = False
    for number, record in enumerate(result.stdout.split(b'\0'), 1):
        if not record:
            continue
        header, raw_name = record.split(b'\t', 1)
        mode, _, stage = header.split()
        name = raw_name.decode('utf-8', 'surrogateescape')
        reasons = []
        if forbidden_path(name):
            reasons.append((0, 'forbidden-path'))
        parts = PurePosixPath(name).parts
        if mode not in (b'100644', b'100755') or stage != b'0':
            reasons.append((0, 'non-regular-or-unmerged-entry'))
        elif not parts or '..' in parts or name.startswith('/'):
            reasons.append((0, 'unsafe-path'))
        else:
            path = root / name
            try:
                if any((root / Path(*parts[:n])).is_symlink() for n in range(1, len(parts) + 1)):
                    reasons.append((0, 'symlink'))
                elif not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > MAX_BYTES:
                    reasons.append((0, 'non-regular-or-oversized-file'))
                else:
                    reasons.extend(findings(path.read_bytes()))
            except OSError:
                reasons.append((0, 'unreadable-tracked-file'))
        for line, reason in reasons:
            print(json.dumps({'entry': number, 'line': line, 'kind': reason}))
            failed = True
    return int(failed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        code = audit(args.repo.resolve())
    except (OSError, ValueError, subprocess.SubprocessError):
        print('Public-tree audit could not complete', file=sys.stderr)
        return 2
    print('Public-tree audit failed' if code else 'Public-tree audit passed')
    return code


if __name__ == '__main__':
    sys.exit(main())
