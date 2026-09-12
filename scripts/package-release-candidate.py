#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare paired release assets locally; do not upload or publish them."""
import argparse
import importlib.util
from pathlib import Path
import shutil
import tarfile
import tempfile

SPEC = importlib.util.spec_from_file_location(
    'stage_candidate', Path(__file__).with_name('stage-candidate.py'))
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)


def package(artifacts, sources, output):
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('existing or symlinked output')
    if any(output.resolve().is_relative_to(p.resolve()) for p in (artifacts, sources)):
        raise ValueError('output must be outside inputs')
    STAGE.checksum(sources / 'THIRD-PARTY-NOTICES.tar')
    # Staging verifies both inventories and binds source and binary manifests.
    with tempfile.TemporaryDirectory(prefix='ls420d-release-') as temp:
        staged = STAGE.stage(artifacts, sources, Path(temp) / 'candidate')
        output.mkdir(parents=True)
        with tarfile.open(output / 'sources.tar', 'x', format=tarfile.PAX_FORMAT) as archive:
            for path in sorted((staged / 'sources').iterdir()):
                info = tarfile.TarInfo(path.name)
                info.size, info.mode, info.mtime = path.stat().st_size, 0o644, 0
                with path.open('rb') as stream:
                    archive.addfile(info, stream)
        for name in ('uImage.buffalo', 'initrd.buffalo', 'build.manifest', 'packages.manifest'):
            shutil.copyfile(staged / name, output / name)
            if STAGE.checksum(staged / name) != STAGE.checksum(output / name):
                raise ValueError('product changed while packaging')
        shutil.copyfile(staged / 'sources' / 'THIRD-PARTY-NOTICES.tar',
                        output / 'THIRD-PARTY-NOTICES.tar')
        # Compare archived sources to the verified staging copy before completing.
        with tarfile.open(output / 'sources.tar') as archive:
            import hashlib
            for member in archive:
                digest = hashlib.sha256()
                with archive.extractfile(member) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(block)
                if digest.hexdigest() != STAGE.checksum(staged / 'sources' / member.name):
                    raise ValueError('source changed while packaging')
        if STAGE.checksum(output / 'THIRD-PARTY-NOTICES.tar') != STAGE.checksum(
                staged / 'sources' / 'THIRD-PARTY-NOTICES.tar'):
            raise ValueError('notices changed while packaging')
        if any(p.stat().st_size >= 2_000_000_000 for p in output.iterdir()):
            raise ValueError('release asset exceeds the supported size')
        (output / 'SHA256SUMS').write_text(''.join(
            f'{STAGE.checksum(path)}  {path.name}\n' for path in sorted(output.iterdir())))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package(args.artifacts, args.sources, args.output)
