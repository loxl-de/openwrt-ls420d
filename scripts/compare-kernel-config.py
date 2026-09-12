#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare Linux configs, rebasing only validated LS420D initramfs input paths."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

KEY = 'CONFIG_INITRAMFS_SOURCE='
BASE = '/target/linux/generic/image/initramfs-base-files.txt'


def normalized(text, required_root=None):
    lines = text.splitlines(keepends=True)
    positions = [i for i, line in enumerate(lines) if line.startswith(KEY)]
    if len(positions) != 1:
        raise ValueError('expected exactly one initramfs source setting')
    index = positions[0]
    match = re.fullmatch(r'CONFIG_INITRAMFS_SOURCE="([^"\\]*)"\n?', lines[index])
    if not match:
        raise ValueError('unsupported initramfs source syntax')
    paths = match[1].split()
    if len(paths) != 2 or not paths[1].endswith(BASE):
        raise ValueError('unexpected initramfs source inputs')
    root = paths[1][:-len(BASE)]
    if (not root.startswith('/') or root == '/'
            or PurePosixPath(root).as_posix() != root
            or '..' in PurePosixPath(root).parts):
        raise ValueError('noncanonical source root')
    if required_root is not None and root != str(required_root):
        raise ValueError('rebuilt initramfs source is outside the expected checkout')
    suffix = paths[0].removeprefix(root)
    if not re.fullmatch(r'/build_dir/target-[A-Za-z0-9_+.-]+/root-mvebu', suffix):
        raise ValueError('unexpected rootfs input')
    if paths[0] != root + suffix:
        raise ValueError('initramfs inputs have different roots')
    ending = '\n' if lines[index].endswith('\n') else ''
    lines[index] = KEY + '"@OPENWRT_SOURCE@' + suffix + ' @OPENWRT_SOURCE@' + BASE + '"' + ending
    return ''.join(lines)


def comparison_report(expected, actual, actual_root):
    report = {
        'format': 1, 'valid_inputs': False, 'match': False,
        'expected_sha256': hashlib.sha256(expected.encode()).hexdigest(),
        'actual_sha256': hashlib.sha256(actual.encode()).hexdigest(),
        'differences': [],
    }
    try:
        left = normalized(expected)
        right = normalized(actual, actual_root)
    except ValueError as error:
        report['validation_error'] = str(error)
        return report
    report['valid_inputs'] = True
    report['match'] = left == right
    report['differences'] = list(difflib.unified_diff(
        left.splitlines(), right.splitlines(),
        fromfile='archived-linux.config', tofile='offline-linux.config', lineterm=''))
    return report


def compare(expected, actual, actual_root):
    report = comparison_report(expected, actual, actual_root)
    if not report['valid_inputs']:
        raise ValueError(report['validation_error'])
    if not report['match']:
        raise ValueError('kernel configurations differ beyond validated source-root relocation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('expected', type=Path)
    parser.add_argument('actual', type=Path)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = comparison_report(args.expected.read_text(), args.actual.read_text(), args.source_root)
    if args.report:
        with args.report.open('x') as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write('\n')
    if not report['valid_inputs']:
        print(report['validation_error'])
        raise SystemExit(2)
    if not report['match']:
        print('\n'.join(report['differences']))
        raise SystemExit(1)
    print('Kernel configs match after validating and rebasing initramfs source roots')
