#!/bin/sh
# SPDX-License-Identifier: MIT

set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)
# shellcheck source=scripts/lib.sh
. "$SCRIPT_DIR/lib.sh"

SOURCE_DIR=${OPENWRT_SOURCE_DIR:-$REPO_ROOT/openwrt-src}
MODE=prepare
case ${1:-} in
    '') ;;
    --checkout-only) MODE=checkout ;;
    --verify-inputs) MODE=verify ;;
    *) fail 'usage: prepare-openwrt.sh [--checkout-only|--verify-inputs]' ;;
esac
[ "$#" -le 1 ] || fail 'usage: prepare-openwrt.sh [--checkout-only|--verify-inputs]'

require_command git
load_openwrt_lock "$REPO_ROOT/openwrt.lock"
validate_feeds_lock "$REPO_ROOT/feeds.lock"

fetch_locked_source() {
    git -C "$SOURCE_DIR" fetch --no-tags --depth=1 origin "$OPENWRT_COMMIT" || return 1
    git -C "$SOURCE_DIR" fetch --no-tags --depth=1 origin \
        "+refs/tags/$OPENWRT_TAG:refs/tags/$OPENWRT_TAG" || return 1
    [ "$(git -C "$SOURCE_DIR" rev-parse "refs/tags/$OPENWRT_TAG")" = "$OPENWRT_TAG_OBJECT" ] ||
        fail "tag object for $OPENWRT_TAG differs from lock"
    [ "$(git -C "$SOURCE_DIR" rev-parse "refs/tags/$OPENWRT_TAG^{}")" = "$OPENWRT_COMMIT" ] ||
        fail "tag $OPENWRT_TAG does not peel to locked commit"
}

if [ ! -d "$SOURCE_DIR/.git" ]; then
    [ ! -e "$SOURCE_DIR" ] || fail "$SOURCE_DIR exists but is not a Git repository"
    mkdir -p "$SOURCE_DIR"
    git -C "$SOURCE_DIR" init -q
    git -C "$SOURCE_DIR" remote add origin "$OPENWRT_SOURCE_URL"
    : > "$SOURCE_DIR/.git/ls420d-managed"
fi

assert_managed_source "$SOURCE_DIR"

if [ -d "$SOURCE_DIR/.git/rebase-apply" ]; then
    git -C "$SOURCE_DIR" am --abort || fail 'unable to recover script-owned checkout from previous git am state'
fi

actual_origin=$(git -C "$SOURCE_DIR" remote get-url origin)
case $actual_origin in
    "$OPENWRT_SOURCE_URL"|"$OPENWRT_FALLBACK_URL") ;;
    *) fail "unexpected OpenWrt origin: $actual_origin" ;;
esac

if ! fetch_locked_source; then
    [ "$actual_origin" = "$OPENWRT_SOURCE_URL" ] || fail 'unable to fetch locked OpenWrt commit'
    printf 'Canonical source unavailable; retrying official GitHub fallback\n' >&2
    git -C "$SOURCE_DIR" remote set-url origin "$OPENWRT_FALLBACK_URL"
    fetch_locked_source || fail 'unable to fetch locked OpenWrt source from either source'
fi

git -C "$SOURCE_DIR" checkout --detach -f "$OPENWRT_COMMIT"
git -C "$SOURCE_DIR" clean -ffdqx
[ "$(git -C "$SOURCE_DIR" rev-parse HEAD)" = "$OPENWRT_COMMIT" ] || fail 'checked-out OpenWrt commit differs from lock'

generate_feeds_conf "$REPO_ROOT/feeds.lock" "$SOURCE_DIR/feeds.conf"
[ "$MODE" != checkout ] || exit 0

if [ "$MODE" = verify ]; then
    verify_tmp=$(mktemp -d "${TMPDIR:-/tmp}/ls420d-feeds.XXXXXX")
    trap 'rm -rf "$verify_tmp"' EXIT HUP INT TERM
    while IFS='|' read -r feed_name feed_url feed_commit feed_extra ||
        [ -n "${feed_name}${feed_url}${feed_commit}${feed_extra}" ]; do
        case $feed_name in ''|'#'*) continue ;; esac
        git -C "$verify_tmp" init -q --bare "$feed_name.git"
        git -C "$verify_tmp/$feed_name.git" fetch --no-tags --depth=1 "$feed_url" "$feed_commit"
        [ "$(git -C "$verify_tmp/$feed_name.git" rev-parse FETCH_HEAD)" = "$feed_commit" ] ||
            fail "fetched feed commit differs from lock: $feed_name"
    done < "$REPO_ROOT/feeds.lock"
    exit 0
fi

apply_patch_series "$SOURCE_DIR" "$REPO_ROOT/openwrt/patches"

for kernel_patch in "$REPO_ROOT"/kernel-patches/*.patch; do
    install -m 0644 "$kernel_patch" "$SOURCE_DIR/target/linux/mvebu/patches-6.12/"
    git -C "$SOURCE_DIR" add "target/linux/mvebu/patches-6.12/$(basename "$kernel_patch")"
done

require_command make
"$SOURCE_DIR/scripts/feeds" update -a
"$SOURCE_DIR/scripts/feeds" install -a
while IFS='|' read -r feed_name feed_url feed_commit feed_extra ||
    [ -n "${feed_name}${feed_url}${feed_commit}${feed_extra}" ]; do
    case $feed_name in ''|'#'*) continue ;; esac
    actual=$(git -C "$SOURCE_DIR/feeds/$feed_name" rev-parse HEAD)
    [ "$actual" = "$feed_commit" ] || fail "feed $feed_name is at $actual, expected $feed_commit"
done < "$REPO_ROOT/feeds.lock"
