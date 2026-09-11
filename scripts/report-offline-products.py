#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Report offline product hashes without masking a configuration mismatch."""
import argparse
import hashlib
import json
from pathlib import Path

PRODUCTS = ('uImage.buffalo', 'initrd.buffalo', 'packages.manifest')


def result(work):
    manifest = dict(line.split('=', 1) for line in
                    (work/'bundle/build.manifest').read_text().splitlines())
    config = json.loads((work/'offline-config-result.json').read_text())
    products = {}
    for name in PRODUCTS:
        actual = hashlib.sha256((work/'artifacts'/name).read_bytes()).hexdigest()
        expected = manifest[f'ARTIFACT_SHA256[{name}]']
        products[name] = {'sha256': actual, 'expected_sha256': expected,
                          'match': actual == expected}
    config_match = config.get('valid_inputs') is True and config.get('match') is True
    products_match = all(p['match'] for p in products.values())
    return {
        'source_zip_sha256': json.loads((work/'RESTORED.json').read_text())['source_zip_sha256'],
        'source_project_commit': manifest['REPOSITORY_COMMIT'],
        'network_isolated': True, 'compiler_cache_used': False,
        'offline_compile_and_packaging_passed': True,
        'kernel_config_match': config_match,
        'products': products, 'all_products_match': products_match,
        'all_checks_passed': config_match and products_match,
        'license_review_complete': False, 'firmware_distribution_authorized': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', type=Path)
    args = parser.parse_args()
    report = result(args.work)
    with (args.work/'offline-result.json').open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report['all_checks_passed']:
        raise SystemExit('offline build completed but configuration or product hashes differ; review required')
