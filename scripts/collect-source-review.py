#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Collect source inputs for review; this does not authorize firmware uploads."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile


FEEDS = {'packages', 'luci', 'routing', 'telephony', 'video'}
SHA1 = re.compile(r'[0-9a-f]{40}')
SOURCE_SUFFIXES = ('.tar.gz', '.tar.bz2', '.tar.xz', '.tar.zst', '.tgz',
                   '.tar', '.zip', '.gz', '.bz2', '.xz', '.zst', '.patch', '.c')


def regular(path):
    """Reject symlinks, including parent symlinks, and incomplete files."""
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlinked input')
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError('missing, empty or non-regular input')
    return path


def digest(path):
    h = hashlib.sha256()
    with regular(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args],
                                   stderr=subprocess.PIPE).decode().strip()


def archive_git(root, expected, destination):
    if not SHA1.fullmatch(expected) or git(root, 'rev-parse', 'HEAD') != expected:
        raise ValueError('source checkout differs from locked commit')
    # Archive committed files, never .git, credentials, worktree output or caches.
    # The project archive separately supplies the patches applied to OpenWrt.
    with destination.open('xb') as stream:
        subprocess.run(['git', '-C', str(root), 'archive', '--format=tar', expected],
                       stdout=stream, stderr=subprocess.PIPE, check=True)


def read_locks(repo):
    values = {}
    for line in regular(repo/'openwrt.lock').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        if key in values:
            raise ValueError('duplicate lock field')
        values[key] = value
    commit = values['OPENWRT_COMMIT']
    if not SHA1.fullmatch(commit):
        raise ValueError('invalid OpenWrt commit')
    feeds = {}
    for line in regular(repo/'feeds.lock').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        name, url, revision = line.split('|')
        if name not in FEEDS or name in feeds or not SHA1.fullmatch(revision):
            raise ValueError('invalid feed lock')
        if not url.startswith('https://'):
            raise ValueError('invalid feed URL')
        feeds[name] = revision
    if set(feeds) != FEEDS:
        raise ValueError('incomplete feed lock')
    return commit, feeds


def download_inputs(directory):
    if not directory.is_dir() or any(p.is_symlink() for p in (directory, *directory.parents)):
        raise ValueError('unsafe download directory')
    paths = sorted(directory.iterdir())
    if not paths:
        raise ValueError('empty source download directory')
    for path in paths:
        regular(path)
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+~-]*', path.name)
                or not path.name.endswith(SOURCE_SUFFIXES)):
            raise ValueError('unexpected download entry; review it before expanding the allowlist')
    return paths


def archive_downloads(paths, destination, epoch):
    inventory = []
    with tarfile.open(destination, 'x', format=tarfile.PAX_FORMAT) as archive:
        for path in paths:
            checksum = digest(path)
            info = tarfile.TarInfo('dl/' + path.name)
            info.size = path.stat().st_size
            info.mode = 0o644
            info.mtime = epoch
            with regular(path).open('rb') as stream:
                archive.addfile(info, stream)
            if digest(path) != checksum:
                raise ValueError('source input changed during collection')
            inventory.append({'name': path.name, 'size': info.size, 'sha256': checksum})
    return inventory


def collect(repo, source, downloads, artifacts, output, notice_selection=None):
    if any(p.is_symlink() for p in (output, *output.parents)) or output.exists():
        raise ValueError('existing or symlinked output')
    if output.resolve().is_relative_to(source.resolve()) or output.resolve().is_relative_to(downloads.resolve()):
        raise ValueError('output must be outside source and downloads')
    if git(repo, 'status', '--porcelain'):
        raise ValueError('project checkout must be clean')
    if not (source/'.git/ls420d-managed').is_file():
        raise ValueError('source checkout is not managed by this project')
    if notice_selection is not None:
        regular(notice_selection)
    commit, feeds = read_locks(repo)
    project_commit = git(repo, 'rev-parse', 'HEAD')
    epoch = int(git(source, 'show', '-s', '--format=%ct', commit))
    linux_configs = list(source.glob('build_dir/target-*/linux-*/linux-*/.config'))
    if len(linux_configs) != 1:
        raise ValueError('expected exactly one resolved Linux configuration')
    metadata = {
        'openwrt.config': source/'.config',
        'linux.config': linux_configs[0],
        'package-metadata.txt': source/'tmp/.packageinfo',
        'target-metadata.txt': source/'tmp/.targetinfo',
        'packages.manifest': artifacts/'packages.manifest',
        'build.manifest': artifacts/'build.manifest',
        'upstream-delta.patch': artifacts/'upstream-delta.patch',
        'runner.txt': artifacts/'runner.txt',
    }
    for path in metadata.values():
        regular(path)
    fields = {}
    for line in metadata['build.manifest'].read_text().splitlines():
        key, value = line.split('=', 1)
        if key in fields:
            raise ValueError('duplicate build manifest field')
        fields[key] = value
    expected = {
        'REPOSITORY_COMMIT': project_commit, 'OPENWRT_COMMIT': commit,
        'CONFIG_SHA256': digest(source/'.config'), 'SOURCE_DATE_EPOCH': str(epoch),
    }
    if any(fields.get(key) != value for key, value in expected.items()):
        raise ValueError('source inputs do not match the firmware build manifest')
    inputs = download_inputs(downloads)
    output.mkdir(parents=True)
    archive_git(repo, project_commit, output/'project.tar')
    archive_git(source, commit, output/'openwrt-upstream.tar')
    for name, revision in sorted(feeds.items()):
        archive_git(source/'feeds'/name, revision, output/f'feed-{name}.tar')
    for name, path in metadata.items():
        shutil.copyfile(path, output/name)
    inventory = archive_downloads(inputs, output/'downloads.tar', epoch)
    report = {
        'format': 1, 'purpose': 'source review candidate, not a firmware release',
        'project_commit': project_commit, 'openwrt_commit': commit,
        'feed_commits': feeds, 'source_date_epoch': epoch,
        'downloads': inventory,
        'offline_rebuild_verified': False, 'license_review_complete': False,
        'firmware_distribution_authorized': False,
    }
    (output/'source-review.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    if notice_selection is not None:
        subprocess.run([
            sys.executable, str(Path(__file__).with_name('collect-notices.py')),
            '--downloads', str(downloads), '--selection', str(notice_selection),
            '--inventory', str(output/'source-review.json'),
            '--output', str(output/'THIRD-PARTY-NOTICES.tar'),
        ], check=True)
    (output/'README.txt').write_text(
        'Source review candidate; no built firmware is included.\n'
        'project.tar contains the build scripts, patches and public overlay.\n'
        'openwrt-upstream.tar and feed-*.tar contain their exact committed sources.\n'
        'downloads.tar contains every archive in this build download directory.\n'
        'Resolved configurations and package metadata accompany these inputs.\n'
        'Git metadata and build outputs are deliberately excluded.\n'
        'Missing inputs, license obligations and offline reconstruction still need review.\n'
        'This is not yet a validated corresponding-source offering.\n')
    shutil.copyfile(repo/'LICENSE', output/'PROJECT-LICENSE.txt')
    (output/'SHA256SUMS').write_text(''.join(
        f'{digest(path)}  {path.name}\n' for path in sorted(output.iterdir())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--downloads', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--notice-selection', type=Path)
    args = parser.parse_args()
    try:
        collect(args.repo, args.source, args.downloads, args.artifacts, args.output, args.notice_selection)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        raise SystemExit('Source collection failed; inspect inputs privately. Do not distribute partial output.')
