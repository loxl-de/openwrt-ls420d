#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify a pinned source-review ZIP and restore it into a fresh directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import tarfile
import zipfile


FEEDS = ('luci', 'packages', 'routing', 'telephony', 'video')
MEMBERS = {
    'PROJECT-LICENSE.txt', 'README.txt', 'SHA256SUMS', 'build.manifest',
    'downloads.tar', 'linux.config', 'openwrt.config', 'package-metadata.txt',
    'packages.manifest', 'project.tar', 'source-review.json', 'runner.txt',
    'target-metadata.txt', 'upstream-delta.patch', 'openwrt-upstream.tar',
    *(f'feed-{name}.tar' for name in FEEDS),
}
LIMIT = 2 * 1024**3


def sha256(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(chunk)
    return h.hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '..' in path.parts
            or '.git' in path.parts or '\\' in name
            or path.as_posix() != name.rstrip('/')):
        raise ValueError('unsafe archive member')
    return path


def extract_tree(archive, output):
    """Allow confined relative symlinks, created only after all regular files."""
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        if sum(m.size for m in members) > LIMIT or len(members) > 100000:
            raise ValueError('archive exceeds limits')
        names = {}
        for member in members:
            name = safe_name(member.name).as_posix()
            if name in names or not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError('duplicate or unsupported archive member')
            names[name] = member
            if member.issym():
                target = member.linkname
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
                if (not target or target.startswith('/') or '\\' in target
                        or resolved == '..' or resolved.startswith('../')
                        or '.git' in PurePosixPath(resolved).parts):
                    raise ValueError('symlink escapes source tree')
        for name in names:
            for parent in PurePosixPath(name).parents:
                if parent.as_posix() in names and not names[parent.as_posix()].isdir():
                    raise ValueError('archive member has non-directory ancestor')
        output.mkdir()
        for name, member in names.items():
            destination = output/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                destination.mkdir(exist_ok=True)
            elif member.isfile():
                with tar.extractfile(member) as src, destination.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
                destination.chmod(0o755 if member.mode & 0o111 else 0o644)
                os.utime(destination, (member.mtime, member.mtime))
        for name, member in names.items():
            if member.issym():
                (output/name).symlink_to(member.linkname)


def restore(archive, expected, output):
    if not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('an independently pinned ZIP SHA-256 is required')
    if any(p.is_symlink() for p in (archive, *archive.parents, output, *output.parents)):
        raise ValueError('symlinked input or output path')
    if output.exists():
        raise ValueError('output already exists')
    with archive.open('rb') as stream:
        if sha256(stream) != expected:
            raise ValueError('source ZIP differs from pinned digest')
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        if len(entries) != len(MEMBERS) or set(z.namelist()) != MEMBERS:
            raise ValueError('unexpected or duplicate ZIP members')
        if sum(i.file_size for i in entries) > LIMIT:
            raise ValueError('ZIP exceeds limits')
        checksums = {}
        for line in z.read('SHA256SUMS').decode().splitlines():
            digest, name = line.split(maxsplit=1)
            if name in checksums or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('invalid checksum inventory')
            checksums[name] = digest
        if set(checksums) != MEMBERS - {'SHA256SUMS'}:
            raise ValueError('incomplete checksum inventory')
        for name, digest in checksums.items():
            with z.open(name) as stream:
                if sha256(stream) != digest:
                    raise ValueError('source member checksum mismatch')
        report = json.loads(z.read('source-review.json'))
        if report['format'] != 1 or set(report['feed_commits']) != set(FEEDS):
            raise ValueError('unsupported source report')
        fields = dict(line.split('=', 1) for line in z.read('build.manifest').decode().splitlines())
        if (fields['REPOSITORY_COMMIT'] != report['project_commit']
                or fields['OPENWRT_COMMIT'] != report['openwrt_commit']
                or fields['CONFIG_SHA256'] != checksums['openwrt.config']
                or fields['SOURCE_DATE_EPOCH'] != str(report['source_date_epoch'])):
            raise ValueError('source report and manifest disagree')
        output.mkdir(parents=True)
        bundle = output/'bundle'
        bundle.mkdir()
        for name in sorted(MEMBERS):
            with z.open(name) as src, (bundle/name).open('xb') as dst:
                shutil.copyfileobj(src, dst)
    extract_tree(bundle/'project.tar', output/'project')
    extract_tree(bundle/'openwrt-upstream.tar', output/'openwrt')
    feeds = output/'openwrt/feeds'
    feeds.mkdir()
    for name in FEEDS:
        extract_tree(bundle/f'feed-{name}.tar', feeds/name)
    extract_tree(bundle/'downloads.tar', output/'downloads')
    actual = {p.name for p in (output/'downloads/dl').iterdir()}
    expected_downloads = {item['name'] for item in report['downloads']}
    if len(expected_downloads) != len(report['downloads']) or actual != expected_downloads:
        raise ValueError('download inventory mismatch')
    for item in report['downloads']:
        path = output/'downloads/dl'/item['name']
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item['size']:
            raise ValueError('invalid restored download')
        with path.open('rb') as stream:
            if sha256(stream) != item['sha256']:
                raise ValueError('restored download digest mismatch')
    (output/'RESTORED.json').write_text(json.dumps({
        'source_zip_sha256': expected, 'project_commit': report['project_commit'],
        'openwrt_commit': report['openwrt_commit'],
        'offline_rebuild_verified': False, 'license_review_complete': False,
    }, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    restore(args.archive, args.sha256, args.output)
