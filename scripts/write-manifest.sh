#!/bin/sh
# SPDX-License-Identifier: MIT

set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=${REPO_ROOT:-$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)}
# shellcheck source=scripts/lib.sh
. "$SCRIPT_DIR/lib.sh"

SOURCE_DIR=${OPENWRT_SOURCE_DIR:-$REPO_ROOT/openwrt-src}
ARTIFACT_DIR=${ARTIFACT_DIR:-$REPO_ROOT/build/artifacts}
: "${SOURCE_DATE_EPOCH:?SOURCE_DATE_EPOCH must be exported before writing the manifest}"
require_command sha256sum
load_openwrt_lock "$REPO_ROOT/openwrt.lock"

for artifact_name in uImage.buffalo initrd.buffalo packages.manifest rootfs-inventory.json upstream-delta.patch public-files.sha256 kernel-patches.sha256; do
    [ -s "$ARTIFACT_DIR/$artifact_name" ] ||
        fail "required packaged artifact is missing: $artifact_name"
done
mkdir -p "$ARTIFACT_DIR"
manifest_tmp=$(mktemp "${TMPDIR:-/tmp}/ls420d-manifest.XXXXXX")
trap 'rm -f "$manifest_tmp"' EXIT HUP INT TERM

target_gcc=$(find "$SOURCE_DIR/staging_dir" -type f -name '*-gcc' -perm -0100 \
    -print 2>/dev/null | LC_ALL=C sort | sed -n '1p')
[ -n "$target_gcc" ] || fail 'target compiler identity is unavailable'
target_compiler=$("$target_gcc" --version | sed -n '1p')

{
    printf 'FORMAT_VERSION=2\n'
    printf 'OPENWRT_VERSION=%s\n' "$OPENWRT_VERSION"
    printf 'OPENWRT_COMMIT=%s\n' "$OPENWRT_COMMIT"
    printf 'SOURCE_DATE_EPOCH=%s\n' "$SOURCE_DATE_EPOCH"
    printf 'REPOSITORY_COMMIT=%s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"
    printf 'OPENWRT_LOCK_SHA256=%s\n' "$(sha256sum "$REPO_ROOT/openwrt.lock" | awk '{print $1}')"
    printf 'FEEDS_LOCK_SHA256=%s\n' "$(sha256sum "$REPO_ROOT/feeds.lock" | awk '{print $1}')"
    printf 'CONFIG_SHA256=%s\n' "$(sha256sum "$SOURCE_DIR/.config" | awk '{print $1}')"
    printf 'TARGET_COMPILER=%s\n' "$target_compiler"
    printf 'PATCH_SERIES_SHA256=%s\n' "$(sha256sum "$REPO_ROOT/openwrt/patches/series" | awk '{print $1}')"
    while IFS= read -r patch_name || [ -n "$patch_name" ]; do
        case $patch_name in ''|'#'*) continue ;; esac
        printf 'PATCH_SHA256[%s]=%s\n' "$patch_name" \
            "$(sha256sum "$REPO_ROOT/openwrt/patches/$patch_name" | awk '{print $1}')"
    done < "$REPO_ROOT/openwrt/patches/series"
    find "$SOURCE_DIR/bin/targets" -type f -name '*.buildinfo' -print 2>/dev/null |
        LC_ALL=C sort | while IFS= read -r buildinfo; do
            relative=${buildinfo#"$SOURCE_DIR/bin/targets/"}
            printf 'BUILDINFO_SHA256[%s]=%s\n' "$relative" \
                "$(sha256sum "$buildinfo" | awk '{print $1}')"
        done
    for artifact_name in uImage.buffalo initrd.buffalo packages.manifest rootfs-inventory.json upstream-delta.patch public-files.sha256 kernel-patches.sha256; do
        printf 'ARTIFACT_SHA256[%s]=%s\n' "$artifact_name" \
            "$(sha256sum "$ARTIFACT_DIR/$artifact_name" | awk '{print $1}')"
    done
} > "$manifest_tmp"
install -m 0644 "$manifest_tmp" "$ARTIFACT_DIR/build.manifest"
(
    cd "$ARTIFACT_DIR"
    sha256sum uImage.buffalo initrd.buffalo packages.manifest rootfs-inventory.json upstream-delta.patch public-files.sha256 kernel-patches.sha256 build.manifest > SHA256SUMS
)
printf 'Wrote %s\n' "$ARTIFACT_DIR/build.manifest"
