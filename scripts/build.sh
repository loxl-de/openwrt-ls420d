#!/bin/sh
# SPDX-License-Identifier: MIT

set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)
# shellcheck source=scripts/lib.sh
. "$SCRIPT_DIR/lib.sh"

SOURCE_DIR=${OPENWRT_SOURCE_DIR:-$REPO_ROOT/openwrt-src}
CONFIG=$REPO_ROOT/config/ls420d.config
[ -z "${OPENWRT_CONFIG:-}" ] || fail 'generic build uses only the versioned public configuration'
ARTIFACT_DIR=${ARTIFACT_DIR:-$REPO_ROOT/build/artifacts}
DOWNLOAD_DIR=${OPENWRT_DOWNLOAD_DIR:-$REPO_ROOT/build/dl}
CCACHE_STORAGE=${OPENWRT_CCACHE_DIR:-$REPO_ROOT/build/ccache}
JOBS=${JOBS:-1}

[ "$#" -eq 0 ] || fail 'public build accepts no private deployment arguments'
[ -z "${ROOTFS_OVERLAY:-}${DEPLOYMENT_CONFIG:-}${SITE_DIR:-}${SECRETS_DIR:-}" ] || fail 'private inputs are forbidden in the public build'

case $JOBS in *[!0-9]*|'') fail 'JOBS must be a positive integer' ;; esac
[ "$JOBS" -gt 0 ] || fail 'JOBS must be a positive integer'
[ -f "$CONFIG" ] || fail "LS420D build configuration is not yet present: $CONFIG"
check_fdtget
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail 'repository must be clean before a release build'

"$SCRIPT_DIR/prepare-openwrt.sh"
"$SCRIPT_DIR/install-public-files.sh"
cp "$CONFIG" "$SOURCE_DIR/.config"
load_openwrt_lock "$REPO_ROOT/openwrt.lock"
SOURCE_DATE_EPOCH=$(git -C "$SOURCE_DIR" show -s --format=%ct "$OPENWRT_COMMIT")
export SOURCE_DATE_EPOCH
make -C "$SOURCE_DIR" defconfig

mkdir -p "$DOWNLOAD_DIR" "$CCACHE_STORAGE"
[ ! -e "$SOURCE_DIR/.ccache" ] || fail 'unexpected ccache path in clean source tree'
ln -s "$CCACHE_STORAGE" "$SOURCE_DIR/.ccache"

make -C "$SOURCE_DIR" -j"$JOBS" DL_DIR="$DOWNLOAD_DIR" download
make -C "$SOURCE_DIR" -j"$JOBS" DL_DIR="$DOWNLOAD_DIR"

kernel_tree=$(find "$SOURCE_DIR/build_dir/target-"* -maxdepth 2 -type d -name 'linux-6.12.*' -print)
[ -n "$kernel_tree" ] || fail 'prepared Linux tree missing'
[ "$(printf '%s\n' "$kernel_tree" | wc -l)" -eq 1 ] || fail 'expected exactly one prepared Linux tree'
python3 "$REPO_ROOT/tests/check-atags.py" "$kernel_tree"

"$SCRIPT_DIR/package-buffalo.sh"
"$SCRIPT_DIR/write-manifest.sh"
