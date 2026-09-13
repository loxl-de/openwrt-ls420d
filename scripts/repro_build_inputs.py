#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain non-executable build-input fingerprints for reproducibility review.

This report deliberately contains hashes and small, validated scalar values only.
It never copies a compiler, object, package, configuration, or build log.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_RECORDS = 512
VERSION_DATE_LIMIT = 256
VERSION_DATE_MAX_BYTES = 256
HOST_TOOLS = (
    'gcc', 'g++', 'ld', 'ld.bfd', 'as', 'collect-ld', 'ar', 'nm',
    'objcopy', 'objdump', 'ranlib', 'readelf', 'strip',
)
TOOL_SUFFIXES = tuple(f'-{name}' for name in (
    'gcc', 'g++', 'ld', 'as', 'ar', 'nm', 'objcopy', 'objdump', 'ranlib',
    'readelf', 'strip'))
GENERATED_NAMES = (
    'auto-host.h', 'config.h', 'config.log', 'config.status', 'Makefile',
    'version.c',
)
PATH_ENVIRONMENT = {
    'PATH', 'OPENWRT_SOURCE_DIR', 'OPENWRT_DOWNLOAD_DIR',
    'OPENWRT_CCACHE_DIR', 'OFFLINE_RESTORED_SOURCE_DIR', 'GIT_CONFIG_GLOBAL',
}
SCALAR_ENVIRONMENT = (
    'SOURCE_DATE_EPOCH', 'JOBS', 'CCACHE_DISABLE', 'GIT_CONFIG_NOSYSTEM',
)
ABSOLUTE_PATH = re.compile(r'(?<![A-Za-z0-9])(?:/[^\s]+)+')
WINDOWS_PATH = re.compile(r'[A-Za-z]:[\\/][^\s]+')
SAFE_VERSION = re.compile(r'^[ -~]{1,240}$')
SAFE_DATE = re.compile(r'^[0-9]+(?:\.[0-9]+)?$')
SAFE_SCALAR = re.compile(r'^[0-9]+(?:\.[0-9]+)?$')


def digest(path):
    """Hash a regular file after enforcing a bounded size."""
    if path.is_symlink() or not path.is_file():
        raise ValueError('diagnostic input is not a regular file')
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError('diagnostic input exceeds size limit')
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
    return size, hasher.hexdigest()


def path_fingerprint(path):
    """Hash an absolute path without placing the path itself in the report."""
    resolved = Path(path).resolve()
    encoded = os.fsencode(str(resolved))
    return {'length': len(encoded), 'sha256': hashlib.sha256(encoded).hexdigest()}


def relative_path(path, root):
    try:
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError('diagnostic path escaped source root') from error


def safe_version_line(path):
    """Return only a sanitized first --version line."""
    try:
        result = subprocess.run([str(path), '--version'], capture_output=True,
                                check=False, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    raw = result.stdout.splitlines() or result.stderr.splitlines()
    if not raw:
        return None
    try:
        line = raw[0].decode('utf-8', 'replace')
    except UnicodeError:
        return None
    line = WINDOWS_PATH.sub('<absolute-path>', line)
    line = ABSOLUTE_PATH.sub('<absolute-path>', line)
    return line if SAFE_VERSION.fullmatch(line) else None


def file_record(path, root, role=None, version=False):
    """Return a hash-only record for a source-contained file."""
    record = {'path': relative_path(path, root)}
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        record['status'] = 'missing'
        if role:
            record['role'] = role
        return record
    if not resolved.is_relative_to(root):
        record['status'] = 'outside-source-root'
        if role:
            record['role'] = role
        return record
    try:
        size, checksum = digest(resolved)
    except (OSError, ValueError):
        record['status'] = 'not-regular-or-oversized'
        if role:
            record['role'] = role
        return record
    record.update(status='ok', size=size, sha256=checksum)
    if role:
        record['role'] = role
    if version:
        record['version_line'] = safe_version_line(resolved)
    return record

def external_file_record(path, role=None, version=False):
    """Hash a PATH-selected file and its resolved path without exposing either."""
    path = Path(path)
    encoded_path = os.fsencode(str(path.resolve()))
    record = {
        'path_length': len(encoded_path),
        'path_sha256': hashlib.sha256(encoded_path).hexdigest(),
    }
    if role:
        record['role'] = role
    try:
        resolved = path.resolve(strict=True)
        size, checksum = digest(resolved)
    except (OSError, ValueError):
        record['status'] = 'missing-or-invalid'
        return record
    record.update(status='ok', size=size, sha256=checksum)
    if version:
        record['version_line'] = safe_version_line(resolved)
    return record


def system_tool_evidence():
    """Capture the runner's PATH-selected host compiler and linker identities."""
    result = []
    for name in ('gcc', 'g++', 'ld'):
        located = shutil.which(name)
        if located:
            result.append(external_file_record(
                located, role='system-' + name, version=True))
        else:
            result.append({'role': 'system-' + name, 'status': 'not-found'})
    return result



def tool_paths(source):
    """Find the final host and target compiler/linker executables."""
    records = []
    host = source/'staging_dir/host/bin'
    for name in HOST_TOOLS:
        path = host/name
        if path.exists() or path.is_symlink():
            records.append((f'host-{name}', path))
    for directory in sorted(source.glob('staging_dir/toolchain-*/bin')):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.name.endswith(TOOL_SUFFIXES) and (path.is_file() or path.is_symlink()):
                records.append(('target-' + path.name, path))
    for directory in sorted(source.glob('build_dir/toolchain-*/gcc-*/gcc')):
        if not directory.is_dir():
            continue
        for name in ('xgcc', 'collect-ld', 'as', 'gcc'):
            path = directory/name
            if path.is_file() or path.is_symlink():
                records.append(('final-gcc-' + name, path))
    if len(records) > MAX_RECORDS:
        raise ValueError('too many compiler tool records')
    return records


def tool_evidence(source):
    result = []
    seen = set()
    for role, path in tool_paths(source):
        key = (role, path.as_posix())
        if key in seen:
            continue
        seen.add(key)
        result.append(file_record(path, source, role=role, version=True))
    result.extend(system_tool_evidence())
    return result


def configuration_evidence(source):
    paths = []
    config = source/'.config'
    if config.exists() or config.is_symlink():
        paths.append(('openwrt-config', config))
    for path in sorted(source.glob('build_dir/target-*/linux-*/linux-*/.config')):
        paths.append(('linux-config', path))
    for tree in sorted(source.glob('build_dir/toolchain-*/gcc-*')):
        directories = [
            ('gcc', tree/'gcc'),
            ('libstdc++-v3', tree/'libstdc++-v3')]
        for directory in sorted(tree.glob('*/libstdc++-v3')):
            directories.append(('libstdc++-v3', directory))
        for subdir, directory in directories:
            for name in GENERATED_NAMES:
                path = directory/name
                if path.exists() or path.is_symlink():
                    paths.append((f'generated-{subdir}', path))
    if len(paths) > MAX_RECORDS:
        raise ValueError('too many generated configuration records')
    return [file_record(path, source, role=role) for role, path in paths]


def version_dates(source):
    paths = sorted(path for path in source.rglob('version.date')
                   if path.is_file() or path.is_symlink())
    if len(paths) > VERSION_DATE_LIMIT:
        raise ValueError('too many version.date files')
    result = []
    for path in paths:
        record = {'path': relative_path(path, source)}
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            record['status'] = 'missing-or-invalid'
            result.append(record)
            continue
        if not resolved.is_relative_to(source):
            raise ValueError('version.date escaped source root')
        if resolved.stat().st_size > VERSION_DATE_MAX_BYTES:
            raise ValueError('version.date exceeds size limit')
        try:
            size, checksum = digest(resolved)
            raw = resolved.read_bytes()
        except (OSError, ValueError):
            record['status'] = 'missing-or-invalid'
            result.append(record)
            continue
        record.update(status='ok', size=size, sha256=checksum)
        try:
            value = raw.decode('ascii').strip()
        except UnicodeDecodeError:
            value = ''
        # The generated file is normally a decimal mtime. Preserve that
        # exact scalar, but never copy arbitrary file content into evidence.
        if SAFE_DATE.fullmatch(value):
            record['value'] = value
        else:
            record['value_status'] = 'non-numeric-hidden'
        result.append(record)
    return result


def environment_evidence():
    result = {}
    for name in SCALAR_ENVIRONMENT + tuple(sorted(PATH_ENVIRONMENT)):
        if name not in os.environ:
            result[name] = {'present': False}
            continue
        value = os.environ[name]
        if name in PATH_ENVIRONMENT:
            encoded = os.fsencode(value)
            result[name] = {
                'present': True, 'length': len(encoded),
                'sha256': hashlib.sha256(encoded).hexdigest(),
            }
        elif SAFE_SCALAR.fullmatch(value):
            result[name] = {'present': True, 'value': value}
        else:
            encoded = os.fsencode(value)
            result[name] = {
                'present': True, 'value_status': 'non-numeric-hidden',
                'length': len(encoded),
                'sha256': hashlib.sha256(encoded).hexdigest(),
            }
    return result


def parse_epoch(explicit):
    raw = str(explicit) if explicit is not None else os.environ.get('SOURCE_DATE_EPOCH', '')
    if not re.fullmatch(r'[0-9]+', raw):
        raise ValueError('SOURCE_DATE_EPOCH must be a non-negative integer')
    value = int(raw)
    return {'value': value, 'utc': datetime.fromtimestamp(value, timezone.utc).isoformat()}


def collect(source, output, work_root=None, project_root=None, source_date_epoch=None):
    if output.exists() or output.is_symlink():
        raise ValueError('diagnostic output already exists')
    if source.is_symlink():
        raise ValueError('source root must not be symlinked')
    source = source.resolve(strict=True)
    if not source.is_dir() or source.is_symlink():
        raise ValueError('source root is not a regular directory')
    roots = {'source': path_fingerprint(source)}
    for label, path in (('work', work_root), ('project', project_root)):
        if path is not None:
            roots[label] = path_fingerprint(path)
    workspace = os.environ.get('GITHUB_WORKSPACE')
    same_workspace_path = False
    if workspace:
        same_workspace_path = source == (Path(workspace).resolve()/'openwrt-src')
    roots['same_workspace_openwrt_src'] = same_workspace_path
    restored = os.environ.get('OFFLINE_RESTORED_SOURCE_DIR')
    if restored:
        roots['restored_source'] = path_fingerprint(restored)
    report = {
        'schema': 1,
        'purpose': 'non-executable reproducibility diagnostics',
        'source_date_epoch': parse_epoch(source_date_epoch),
        'roots': roots,
        'environment': environment_evidence(),
        'configurations': configuration_evidence(source),
        'version_dates': version_dates(source),
        'tools': tool_evidence(source),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--work-root', type=Path)
    parser.add_argument('--project-root', type=Path)
    parser.add_argument('--source-date-epoch', type=int)
    args = parser.parse_args()
    try:
        report = collect(args.source_root, args.output, args.work_root,
                         args.project_root, args.source_date_epoch)
    except (OSError, ValueError, OverflowError):
        raise SystemExit('Build-input evidence failed; inspect inputs privately') from None
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
