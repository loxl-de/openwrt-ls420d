#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
repo=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
: "${OPENWRT_SOURCE_DIR:=$repo/openwrt-src}"
[ ! -e "$OPENWRT_SOURCE_DIR/files" ] || { echo 'Unexpected pre-existing files overlay' >&2; exit 1; }
mkdir "$OPENWRT_SOURCE_DIR/files"
cp -R "$repo/openwrt/files/." "$OPENWRT_SOURCE_DIR/files/"
find "$OPENWRT_SOURCE_DIR/files" -type d -exec chmod 0755 {} +
find "$OPENWRT_SOURCE_DIR/files" -type f -exec chmod 0644 {} +
chmod 0755 "$OPENWRT_SOURCE_DIR/files/etc/init.d/ls420d-phy" \
    "$OPENWRT_SOURCE_DIR/files/etc/init.d/ls420d-fan" \
    "$OPENWRT_SOURCE_DIR/files/usr/sbin/ls420d-fan" \
    "$OPENWRT_SOURCE_DIR/files/etc/uci-defaults/50-ls420d-site" \
    "$OPENWRT_SOURCE_DIR/files/etc/uci-defaults/99-ls420d-runtime"
