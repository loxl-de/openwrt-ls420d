#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare Linux configs, rebasing only validated LS420D initramfs input paths."""
import argparse
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


def compare(expected, actual, actual_root):
    if normalized(expected) != normalized(actual, actual_root):
        raise ValueError('kernel configurations differ beyond validated source-root relocation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('expected', type=Path)
    parser.add_argument('actual', type=Path)
    parser.add_argument('--source-root', required=True, type=Path)
    args = parser.parse_args()
    compare(args.expected.read_text(), args.actual.read_text(), args.source_root)
    print('Kernel configs match after validating and rebasing initramfs source roots')
