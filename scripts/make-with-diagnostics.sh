#!/bin/sh
# SPDX-License-Identifier: MIT
# Preserve a parallel failure even if its diagnostic serial rerun succeeds.
set -u
make "$@"
result=$?
if [ "$result" -ne 0 ]; then
    echo 'Build failed; repeating the same target serially with verbose diagnostics' >&2
    make "$@" -j1 V=s || :
fi
exit "$result"
