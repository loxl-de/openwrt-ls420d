#!/bin/sh
# SPDX-License-Identifier: MIT

set -eu

fail() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

is_sha1() {
    case $1 in
        *[!0-9a-f]*|'') return 1 ;;
    esac
    [ "${#1}" -eq 40 ]
}

is_https_git_url() {
    case $1 in
        https://*.git) return 0 ;;
        *) return 1 ;;
    esac
}

load_openwrt_lock() {
    lock_file=$1
    [ -f "$lock_file" ] || fail "lock file not found: $lock_file"

    OPENWRT_VERSION=''
    OPENWRT_TAG=''
    OPENWRT_TAG_OBJECT=''
    OPENWRT_COMMIT=''
    OPENWRT_SOURCE_URL=''
    OPENWRT_FALLBACK_URL=''
    seen_keys=' '

    while IFS= read -r lock_line || [ -n "$lock_line" ]; do
        case $lock_line in ''|'#'*) continue ;; esac
        case $lock_line in *=*) ;; *) fail "invalid lock line: $lock_line" ;; esac
        lock_key=${lock_line%%=*}
        lock_value=${lock_line#*=}
        [ -n "$lock_value" ] || fail "empty lock value: $lock_key"
        case $lock_key in *[!A-Z_]*) fail "invalid lock key: $lock_key" ;; esac
        case $seen_keys in *" $lock_key "*) fail "duplicate lock key: $lock_key" ;; esac
        seen_keys="$seen_keys$lock_key "
        case $lock_key in
            OPENWRT_VERSION) OPENWRT_VERSION=$lock_value ;;
            OPENWRT_TAG) OPENWRT_TAG=$lock_value ;;
            OPENWRT_TAG_OBJECT) OPENWRT_TAG_OBJECT=$lock_value ;;
            OPENWRT_COMMIT) OPENWRT_COMMIT=$lock_value ;;
            OPENWRT_SOURCE_URL) OPENWRT_SOURCE_URL=$lock_value ;;
            OPENWRT_FALLBACK_URL) OPENWRT_FALLBACK_URL=$lock_value ;;
            *) fail "unknown lock key: $lock_key" ;;
        esac
    done < "$lock_file"

    for lock_key in OPENWRT_VERSION OPENWRT_TAG OPENWRT_TAG_OBJECT OPENWRT_COMMIT OPENWRT_SOURCE_URL OPENWRT_FALLBACK_URL; do
        case $seen_keys in *" $lock_key "*) ;; *) fail "missing lock key: $lock_key" ;; esac
    done
    case $OPENWRT_VERSION in *[!0-9.]*) fail 'invalid OPENWRT_VERSION' ;; esac
    [ "$OPENWRT_TAG" = "v$OPENWRT_VERSION" ] || fail 'OPENWRT_TAG must match OPENWRT_VERSION'
    is_sha1 "$OPENWRT_TAG_OBJECT" || fail 'OPENWRT_TAG_OBJECT must be a full SHA-1'
    is_sha1 "$OPENWRT_COMMIT" || fail 'OPENWRT_COMMIT must be a full SHA-1'
    is_https_git_url "$OPENWRT_SOURCE_URL" || fail 'invalid OPENWRT_SOURCE_URL'
    is_https_git_url "$OPENWRT_FALLBACK_URL" || fail 'invalid OPENWRT_FALLBACK_URL'
}

validate_feeds_lock() {
    feeds_file=$1
    [ -f "$feeds_file" ] || fail "feeds lock not found: $feeds_file"
    expected=' packages luci routing telephony video '
    seen=' '
    count=0
    while IFS='|' read -r feed_name feed_url feed_commit feed_extra ||
        [ -n "${feed_name}${feed_url}${feed_commit}${feed_extra}" ]; do
        case $feed_name in ''|'#'*) continue ;; esac
        [ -z "$feed_extra" ] || fail "too many fields for feed: $feed_name"
        case $feed_name in *[!a-z0-9_-]*) fail "invalid feed name: $feed_name" ;; esac
        case $expected in *" $feed_name "*) ;; *) fail "unknown feed: $feed_name" ;; esac
        case $seen in *" $feed_name "*) fail "duplicate feed: $feed_name" ;; esac
        is_https_git_url "$feed_url" || fail "invalid feed URL: $feed_name"
        is_sha1 "$feed_commit" || fail "invalid feed commit: $feed_name"
        seen="$seen$feed_name "
        count=$((count + 1))
    done < "$feeds_file"
    [ "$count" -eq 5 ] || fail 'feeds lock must contain all five expected feeds'
}

generate_feeds_conf() {
    feeds_file=$1
    output=$2
    : > "$output"
    while IFS='|' read -r feed_name feed_url feed_commit feed_extra ||
        [ -n "${feed_name}${feed_url}${feed_commit}${feed_extra}" ]; do
        case $feed_name in ''|'#'*) continue ;; esac
        printf 'src-git %s %s^%s\n' "$feed_name" "$feed_url" "$feed_commit" >> "$output"
    done < "$feeds_file"
}

assert_managed_source() {
    source_dir=$1
    [ -f "$source_dir/.git/ls420d-managed" ] ||
        fail "$source_dir is not a checkout created by prepare-openwrt.sh"
}

apply_patch_series() {
    source_dir=$1
    patches_dir=$2
    series_file=$patches_dir/series
    [ -f "$series_file" ] || fail "patch series missing: $series_file"
    listed=' '
    while IFS= read -r patch_name || [ -n "$patch_name" ]; do
        case $patch_name in ''|'#'*) continue ;; esac
        case $patch_name in */*|*'..'*) fail "invalid patch name in series: $patch_name" ;; esac
        [ -f "$patches_dir/$patch_name" ] || fail "listed patch missing: $patch_name"
        case $listed in *" $patch_name "*) fail "duplicate patch in series: $patch_name" ;; esac
        listed="$listed$patch_name "
        git -C "$source_dir" apply --index "$patches_dir/$patch_name" ||
            fail "failed to apply patch: $patch_name"
    done < "$series_file"
    for patch_path in "$patches_dir"/*.patch; do
        [ -e "$patch_path" ] || break
        patch_name=${patch_path##*/}
        case $listed in *" $patch_name "*) ;; *) fail "unlisted patch file: $patch_name" ;; esac
    done
}

# Print "version tag_object commit" for the newest release tag of a
# major.minor series, reading `git ls-remote --tags` output on stdin.
# Only plain vX.Y.Z tags count; release candidates and other suffixes do not.
newest_release_tag() {
    series=$1
    case $series in *[!0-9.]*|'') fail 'invalid release series' ;; esac
    best_patch=-1
    best_version=''
    best_object=''
    while IFS='	' read -r object ref; do
        case $ref in "refs/tags/v$series."*) ;; *) continue ;; esac
        case $ref in *'^{}') continue ;; esac
        patch=${ref#refs/tags/v"$series".}
        case $patch in *[!0-9]*|'') continue ;; esac
        is_sha1 "$object" || fail "invalid tag object in remote listing: $ref"
        if [ "$patch" -gt "$best_patch" ]; then
            best_patch=$patch
            best_version=$series.$patch
            best_object=$object
        fi
    done
    [ -n "$best_version" ] || fail "no release tag found for series $series"
    printf '%s %s\n' "$best_version" "$best_object"
}

# Look up the peeled commit of a tag in `git ls-remote --tags` output on stdin.
peeled_tag_commit() {
    tag=$1
    while IFS='	' read -r object ref; do
        [ "$ref" = "refs/tags/$tag^{}" ] || continue
        is_sha1 "$object" || fail "invalid peeled commit for $tag"
        printf '%s\n' "$object"
        return 0
    done
    fail "tag $tag is not an annotated tag with a peeled commit"
}

# Rewrite a feeds lock with the commits from an upstream feeds.conf.default,
# keeping the source URLs already chosen in the current lock.
feeds_lock_from_conf() {
    conf_file=$1
    current_lock=$2
    output=$3
    version=$4
    {
        printf '# SPDX-License-Identifier: MIT\n'
        printf '# name|source URL|commit from OpenWrt v%s feeds.conf.default\n' "$version"
        while IFS='|' read -r feed_name feed_url feed_commit feed_extra ||
            [ -n "${feed_name}${feed_url}${feed_commit}${feed_extra}" ]; do
            case $feed_name in ''|'#'*) continue ;; esac
            feed_new_commit=$(awk -v name="$feed_name" '
                ($1 == "src-git" || $1 == "src-git-full") && $2 == name {
                    split($3, parts, "^"); print parts[2]; exit
                }' "$conf_file")
            is_sha1 "$feed_new_commit" || fail "feed $feed_name has no pinned commit in feeds.conf.default"
            printf '%s|%s|%s\n' "$feed_name" "$feed_url" "$feed_new_commit"
        done < "$current_lock"
    } > "$output"
    validate_feeds_lock "$output"
}
