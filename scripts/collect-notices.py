#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Copy selected original notices into a review archive; never authorize release."""
import argparse
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile


def digest(path):
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('non-regular or symlinked source')
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


@contextmanager
def source_tar(path):
    if path.name.endswith('.zst'):
        # Stream decompression: GCC/Linux source archives need not fit in RAM.
        with subprocess.Popen(['zstd', '-dc', str(path)], stdout=subprocess.PIPE) as proc:
            try:
                with tarfile.open(fileobj=proc.stdout, mode='r|') as archive:
                    yield archive
                # Consume tar padding too, before checking decompressor success.
                while proc.stdout.read(1024 * 1024):
                    pass
                proc.stdout.close()
                if proc.wait() != 0:
                    raise ValueError('source decompression failed')
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
    else:
        with tarfile.open(path, mode='r|*') as archive:
            yield archive


def discover(downloads, inventory, selection):
    """Include named notices from every supplied source archive."""
    records = {(f['source'], f['member']): f for f in selection['files']}
    if len(records) != len(selection['files']):
        raise ValueError('duplicate notice selection')
    seen = set()
    for entry in inventory['downloads']:
        source, expected = entry['name'], entry['sha256']
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+~-]*', source)
                or not re.fullmatch(r'[0-9a-f]{64}', expected) or source in seen):
            raise ValueError('invalid or duplicate source inventory entry')
        seen.add(source)
        path = downloads / source
        if digest(path) != expected:
            raise ValueError('source archive checksum mismatch')
        members = set()
        with source_tar(path) as archive:
            for member in archive:
                parts = PurePosixPath(member.name)
                named = re.fullmatch(
                    r'(copying|copyright|license|licence|notice)([._-].*)?',
                    parts.name, re.IGNORECASE)
                nested = any(p.lower() in ('licenses', 'licences')
                             for p in parts.parts[:-1])
                if not (named or nested) or not member.isfile():
                    continue
                if member.name in members or member.size > 8 * 1024 * 1024:
                    raise ValueError('duplicate or oversized notice')
                members.add(member.name)
                blob = archive.extractfile(member).read()
                item = {'source': source, 'source_sha256': expected,
                        'member': member.name, 'sha256': hashlib.sha256(blob).hexdigest()}
                key = (source, member.name)
                if key in records and any(records[key][k] != v for k, v in item.items()):
                    raise ValueError('selected notice differs from supplied source')
                records.setdefault(key, item)
        if digest(path) != expected:
            raise ValueError('source changed during notice discovery')
    if any(source not in seen for source, _ in records):
        raise ValueError('selected source missing from inventory')
    return {'files': [records[key] for key in sorted(records)]}


def collect(downloads, selection, output):
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('existing or symlinked output')
    groups = {}
    seen = set()
    for item in selection['files']:
        source, member = item['source'], item['member']
        parts = PurePosixPath(member)
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+~-]*', source)
                or parts.is_absolute() or '..' in parts.parts
                or not member or '\\' in member or str(parts) != member):
            raise ValueError('unsafe notice path')
        for key in ('source_sha256', 'sha256'):
            if not re.fullmatch(r'[0-9a-f]{64}', item[key]):
                raise ValueError('invalid notice checksum')
        if (source, member) in seen:
            raise ValueError('duplicate notice selection')
        seen.add((source, member))
        groups.setdefault(source, []).append(item)
    if not seen:
        raise ValueError('empty notice selection')
    payloads = {}
    for source, items in sorted(groups.items()):
        path = downloads / source
        expected = {item['source_sha256'] for item in items}
        if len(expected) != 1 or digest(path) not in expected:
            raise ValueError('source archive checksum mismatch')
        wanted = {item['member']: item for item in items}
        found = set()
        with source_tar(path) as archive:
            for member in archive:
                if member.name not in wanted:
                    continue
                if member.name in found or not member.isfile() or member.size > 8 * 1024 * 1024:
                    raise ValueError('duplicate, linked or oversized notice')
                blob = archive.extractfile(member).read()
                if hashlib.sha256(blob).hexdigest() != wanted[member.name]['sha256']:
                    raise ValueError('notice checksum mismatch')
                payloads[f'notices/{source}/{member.name}'] = blob
                found.add(member.name)
        if found != set(wanted) or digest(path) not in expected:
            raise ValueError('missing notice or changed source archive')
    report = {'scope': 'Selected original notices; not a completeness or release approval.',
              'files': sorted(selection['files'], key=lambda x: (x['source'], x['member']))}
    payloads['INDEX.json'] = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    # Validate every input before creating the exclusive output. No extraction to disk.
    with tarfile.open(output, 'x', format=tarfile.PAX_FORMAT) as archive:
        for name, blob in sorted(payloads.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(blob), 0o644, 0
            archive.addfile(info, io.BytesIO(blob))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--downloads', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, help='Source-review inventory for named notices')
    args = parser.parse_args()
    digest(args.selection)
    selection = json.loads(args.selection.read_text())
    if args.inventory:
        digest(args.inventory)
        selection = discover(args.downloads, json.loads(args.inventory.read_text()), selection)
    collect(args.downloads, selection, args.output)
