#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export an allowlisted text-only report, never firmware or arbitrary files."""
import hashlib
import importlib.util
from pathlib import Path
import shutil
import sys

PRODUCTS = ('uImage.buffalo', 'initrd.buffalo', 'packages.manifest',
            'rootfs-inventory.json', 'upstream-delta.patch', 'public-files.sha256',
            'kernel-patches.sha256', 'build.manifest', 'SHA256SUMS')
TEXT = ('packages.manifest', 'rootfs-inventory.json', 'upstream-delta.patch',
        'public-files.sha256', 'kernel-patches.sha256', 'build.manifest', 'runner.txt')
SPEC = importlib.util.spec_from_file_location('public_audit', Path(__file__).with_name('audit-public-tree.py'))
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def digest(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise ValueError('missing, empty or symlinked product')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def export(source, output):
    if source.is_symlink() or output.exists():
        raise ValueError('unsafe source or existing output directory')
    hashes = {name: digest(source/name) for name in PRODUCTS}
    # Validate all public text before creating anything. Unexpected files are
    # not selected, even if a future build adds a private companion/archive.
    texts = {}
    for name in TEXT:
        digest(source/name)
        if (source/name).stat().st_size > AUDIT.MAX_BYTES:
            raise ValueError('oversized report')
        value = (source/name).read_bytes()
        if AUDIT.findings(value):
            raise ValueError('report failed privacy scan')
        value.decode('utf-8')
        texts[name] = value
    output.mkdir(parents=True)
    for name, value in texts.items():
        (output/name).write_bytes(value)
    (output/'products.sha256').write_text(''.join(
        f'{hashes[name]}  {name}\n' for name in PRODUCTS))
    (output/'README.txt').write_text(
        'Compile-only evidence, NOT a bootable firmware bundle.\n'
        'Firmware was built and hashed on this runner but is not uploaded.\n'
        'Corresponding-source and license review must precede binary distribution.\n'
        'Matching hashes from independent runners do not establish hardware support.\n')
    license_file = Path(__file__).resolve().parents[1]/'LICENSES/GPL-2.0'
    shutil.copyfile(license_file, output/'GPL-2.0.txt')
    shutil.copyfile(Path(__file__).resolve().parents[1]/'LICENSE', output/'MIT.txt')
    (output/'EVIDENCE-SHA256SUMS').write_text(''.join(
        f'{digest(p)}  {p.name}\n' for p in sorted(output.iterdir())))


if __name__ == '__main__':
    try:
        if len(sys.argv) != 3:
            raise ValueError('expected source and fresh output directory')
        export(Path(sys.argv[1]), Path(sys.argv[2]))
    except (OSError, ValueError):
        raise SystemExit('Compile evidence export failed; inspect inputs privately')
