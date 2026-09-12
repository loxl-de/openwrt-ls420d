#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pair firmware with its collected sources for local review, without publishing."""
import argparse
import hashlib
from pathlib import Path
import re
import shutil


def checksum(path):
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('non-regular or symlinked input')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def stage(artifacts, sources, output):
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('output already exists or is symlinked')
    for root in (artifacts, sources):
        if output.resolve().is_relative_to(root.resolve()):
            raise ValueError('output must be outside inputs')
    checksum(sources / 'SHA256SUMS')
    entries = {}
    for line in (sources / 'SHA256SUMS').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)', line)
        if not match or match[2] in entries or match[2] == 'SHA256SUMS':
            raise ValueError('invalid source inventory')
        entries[match[2]] = match[1]
    required = {'project.tar', 'openwrt-upstream.tar', 'downloads.tar',
                'build.manifest', 'packages.manifest', 'source-review.json',
                'openwrt.config', 'linux.config', 'PROJECT-LICENSE.txt'}
    required.update(f'feed-{name}.tar' for name in
                    ('packages', 'luci', 'routing', 'telephony', 'video'))
    if not required <= entries.keys():
        raise ValueError('incomplete source inventory')
    if {p.name for p in sources.iterdir()} != set(entries) | {'SHA256SUMS'}:
        raise ValueError('unlisted source input')
    for name, expected in entries.items():
        if checksum(sources / name) != expected:
            raise ValueError('source checksum mismatch')
    if checksum(artifacts / 'build.manifest') != entries['build.manifest']:
        raise ValueError('sources belong to a different build')
    fields = {}
    for line in (artifacts / 'build.manifest').read_text().splitlines():
        key, value = line.split('=', 1)
        if key in fields:
            raise ValueError('duplicate manifest field')
        fields[key] = value
    products = ('uImage.buffalo', 'initrd.buffalo', 'packages.manifest')
    for name in products:
        if checksum(artifacts / name) != fields.get(f'ARTIFACT_SHA256[{name}]'):
            raise ValueError('product checksum mismatch')
    if checksum(artifacts / 'packages.manifest') != entries['packages.manifest']:
        raise ValueError('package inventory mismatch')
    output.mkdir(parents=True)
    shutil.copytree(sources, output / 'sources')
    for name in (*products, 'build.manifest'):
        shutil.copyfile(artifacts / name, output / name)
    # Verify the copies before writing the inventory that marks a complete pair.
    for name, expected in entries.items():
        if checksum(output / 'sources' / name) != expected:
            raise ValueError('source changed during staging')
    for name in products:
        if checksum(output / name) != fields[f'ARTIFACT_SHA256[{name}]']:
            raise ValueError('product changed during staging')
    if checksum(output / 'build.manifest') != entries['build.manifest']:
        raise ValueError('manifest changed during staging')
    (output / 'SHA256SUMS').write_text(''.join(
        f'{checksum(path)}  {path.relative_to(output).as_posix()}\n'
        for path in sorted(output.rglob('*')) if path.is_file()))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    stage(args.artifacts, args.sources, args.output)
