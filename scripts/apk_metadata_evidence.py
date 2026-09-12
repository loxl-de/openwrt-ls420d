#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fingerprint APK metadata without publishing scalar values or script bodies."""
import hashlib
import json


def fingerprint(value):
    """Keep JSON structure; hash all scalar values and object keys."""
    if isinstance(value, dict):
        return {hashlib.sha256(key.encode('utf-8')).hexdigest(): fingerprint(item)
                for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [fingerprint(item) for item in value]
    raw = json.dumps(value, ensure_ascii=True, allow_nan=False,
                     separators=(',', ':')).encode('ascii')
    return {'type': type(value).__name__, 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    import sys
    limit = 16 * 1024 * 1024
    raw = sys.stdin.buffer.read(limit + 1)
    if len(raw) > limit:
        raise SystemExit('APK metadata exceeds diagnostic size limit')
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate metadata object key')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        result = fingerprint(value)
    except (ValueError, RecursionError, UnicodeError):
        raise SystemExit('invalid APK metadata JSON') from None
    print(json.dumps({'schema': 1, 'metadata': result}, sort_keys=True))


if __name__ == '__main__':
    main()
