#!/bin/sh
# SPDX-License-Identifier: MIT
# Requires the pinned Gitleaks CLI. Do not forward scanner diagnostics: even
# redaction cannot promise to hide a secret used as a filename or commit title.
set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)
SCANNER=${GITLEAKS:-gitleaks}
"$SCANNER" version >/dev/null 2>&1 || { echo 'Secret scanner unavailable' >&2; exit 2; }
"$SCANNER" git --no-banner --redact=100 --log-opts=--all --max-archive-depth=3 \
    --max-decode-depth=3 "$REPO_ROOT" >/dev/null 2>&1 || {
    echo 'History secret scan failed; inspect privately with redaction enabled' >&2
    exit 1
}
echo 'History secret scan passed'
