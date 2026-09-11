#!/bin/sh
# SPDX-License-Identifier: MIT
# Propose the newest point release of the locked OpenWrt series. Rewrites
# openwrt.lock and feeds.lock in place; never floats a build automatically.
# The result is a change for review, not a release.

set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)
# shellcheck source=scripts/lib.sh
. "$SCRIPT_DIR/lib.sh"

MODE=bump
case ${1:-} in
    '') ;;
    --check) MODE=check ;;
    *) fail 'usage: bump-openwrt-lock.sh [--check]' ;;
esac
[ "$#" -le 1 ] || fail 'usage: bump-openwrt-lock.sh [--check]'

require_command git
require_command awk
load_openwrt_lock "$REPO_ROOT/openwrt.lock"
validate_feeds_lock "$REPO_ROOT/feeds.lock"
series=${OPENWRT_VERSION%.*}

work=$(mktemp -d "${TMPDIR:-/tmp}/ls420d-bump.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

list_tags() {
    git ls-remote --tags "$1" "refs/tags/v$series.*" > "$work/tags" 2>/dev/null &&
        [ -s "$work/tags" ]
}
if ! list_tags "$OPENWRT_SOURCE_URL"; then
    printf 'Canonical source unavailable; using official GitHub fallback\n' >&2
    list_tags "$OPENWRT_FALLBACK_URL" || fail 'unable to list release tags from either source'
    source_url=$OPENWRT_FALLBACK_URL
else
    source_url=$OPENWRT_SOURCE_URL
fi

newest=$(newest_release_tag "$series" < "$work/tags")
new_version=${newest%% *}
new_object=${newest#* }
new_tag=v$new_version
new_commit=$(peeled_tag_commit "$new_tag" < "$work/tags")

if [ "$new_version" = "$OPENWRT_VERSION" ]; then
    printf 'UP_TO_DATE=%s\n' "$OPENWRT_VERSION"
    exit 0
fi
[ "${new_version##*.}" -gt "${OPENWRT_VERSION##*.}" ] ||
    fail "newest remote release $new_version is older than the lock"
printf 'UPDATE_AVAILABLE=%s\n' "$new_version"
[ "$MODE" = bump ] || exit 0

git -C "$work" init -q --bare upstream.git
git -C "$work/upstream.git" fetch -q --no-tags --depth=1 "$source_url" "refs/tags/$new_tag:refs/tags/$new_tag"
[ "$(git -C "$work/upstream.git" rev-parse "refs/tags/$new_tag")" = "$new_object" ] ||
    fail "fetched tag object for $new_tag differs from the remote listing"
[ "$(git -C "$work/upstream.git" rev-parse "refs/tags/$new_tag^{}")" = "$new_commit" ] ||
    fail "tag $new_tag does not peel to the listed commit"
git -C "$work/upstream.git" show "$new_commit:feeds.conf.default" > "$work/feeds.conf.default"

feeds_lock_from_conf "$work/feeds.conf.default" "$REPO_ROOT/feeds.lock" "$work/feeds.lock" "$new_version"
{
    printf '# SPDX-License-Identifier: MIT\n'
    printf 'OPENWRT_VERSION=%s\n' "$new_version"
    printf 'OPENWRT_TAG=%s\n' "$new_tag"
    printf 'OPENWRT_TAG_OBJECT=%s\n' "$new_object"
    printf 'OPENWRT_COMMIT=%s\n' "$new_commit"
    printf 'OPENWRT_SOURCE_URL=%s\n' "$OPENWRT_SOURCE_URL"
    printf 'OPENWRT_FALLBACK_URL=%s\n' "$OPENWRT_FALLBACK_URL"
} > "$work/openwrt.lock"
load_openwrt_lock "$work/openwrt.lock"
install -m 0644 "$work/openwrt.lock" "$REPO_ROOT/openwrt.lock"
install -m 0644 "$work/feeds.lock" "$REPO_ROOT/feeds.lock"
printf 'Updated openwrt.lock and feeds.lock to OpenWrt %s (%s)\n' "$new_version" "$new_commit" >&2
