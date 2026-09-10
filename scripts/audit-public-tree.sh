#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/audit-public-tree.py" "$@"
