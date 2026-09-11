#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inventory package license declarations; never infer distribution approval."""
import argparse
import json
from pathlib import Path
import re


def metadata_records(text):
    records = []
    record = None
    recipe = ''
    in_description = False
    for line in text.splitlines():
        if line == '@@':
            in_description = False
            continue
        if in_description:
            continue
        if line.startswith('Source-Makefile: '):
            recipe = line.partition(': ')[2]
        if line.startswith('Package: '):
            if record:
                records.append(record)
            record = {'recipe': recipe, 'Package': line.partition(': ')[2]}
        elif record and re.match(r'^[A-Za-z][A-Za-z-]*:', line):
            key, _, value = line.partition(':')
            record[key] = value.strip()
            in_description = key == 'Description'
    if record:
        records.append(record)
    return records


def binary_name(record):
    name, abi = record['Package'], record.get('ABI-Version', '')
    # OpenWrt separates an ABI suffix from a package name ending in a digit.
    if name.startswith('kmod-'):
        return name
    return name + ('-' if abi and name[-1].isdigit() else '') + abi


def review(manifest, metadata):
    records = metadata_records(metadata)
    selected = []
    seen = set()
    for line in manifest.splitlines():
        name, version = line.split(' - ', 1)
        if name in seen or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.+_-]*', name):
            raise ValueError('invalid or duplicate installed package')
        seen.add(name)
        candidates = [r for r in records if binary_name(r) == name]
        if not candidates:
            candidates = [r for r in records if r['Package'] == name]
        item = {'package': name, 'installed_version': version, 'review_complete': False}
        if len(candidates) != 1:
            item['finding'] = 'missing metadata' if not candidates else 'ambiguous metadata'
        else:
            record = candidates[0]
            item.update(recipe=record['recipe'], declared_license=record.get('License', ''),
                        declared_license_files=record.get('LicenseFiles', '').split(),
                        declared_source=record.get('Source', ''),
                        metadata_version=record.get('Version', ''))
            if not item['declared_license']:
                item['finding'] = 'missing license declaration'
            elif not item['declared_license_files']:
                item['finding'] = 'no explicit LicenseFiles field; inspect source notices'
        selected.append(item)
    return {'format': 1, 'package_count': len(selected), 'packages': selected,
            'scope': 'installed target package declarations, not complete notice or license review',
            'kernel_and_host_toolchain_review_complete': False,
            'license_review_complete': False, 'firmware_distribution_authorized': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_bundle', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = review((args.source_bundle/'packages.manifest').read_text(),
                    (args.source_bundle/'package-metadata.txt').read_text())
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
