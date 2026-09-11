#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
[ "$#" -eq 1 ] || { echo 'usage: rebuild-offline.sh RESTORED_DIRECTORY' >&2; exit 1; }
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
work=$(CDPATH='' cd -- "$1" && pwd)
[ -f "$work/RESTORED.json" ] || { echo 'source restoration was not verified' >&2; exit 1; }

# The workflow supplies an empty network namespace, then drops back to the
# ordinary runner user. Fail rather than silently running this test online.
python3 "$script_dir/check-offline-network.py"
[ "$(id -u)" -ne 0 ] || { echo 'do not compile as root' >&2; exit 1; }

project=$work/project
export OPENWRT_SOURCE_DIR="$work/openwrt"
export ARTIFACT_DIR="$work/artifacts"
export SOURCE_DATE_EPOCH
SOURCE_DATE_EPOCH=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source_date_epoch"])' "$work/bundle/source-review.json")
export CCACHE_DISABLE=1
export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL=/dev/null
JOBS=${JOBS:-4}
case $JOBS in ''|*[!0-9]*) exit 1 ;; esac
[ "$JOBS" -gt 0 ] || exit 1

# Only a scratch baseline for git apply/diff, not a reconstruction of history.
# The archived version file supplies OpenWrt's original revision string.
[ -s "$OPENWRT_SOURCE_DIR/version" ] || { echo 'archived revision file missing' >&2; exit 1; }
[ ! -e "$OPENWRT_SOURCE_DIR/.git" ] || { echo 'source directory is not fresh' >&2; exit 1; }
git -C "$OPENWRT_SOURCE_DIR" init -q
git -C "$OPENWRT_SOURCE_DIR" add --force --all -- . ':!feeds'
GIT_AUTHOR_DATE="@$SOURCE_DATE_EPOCH +0000" GIT_COMMITTER_DATE="@$SOURCE_DATE_EPOCH +0000" \
    git -C "$OPENWRT_SOURCE_DIR" -c user.name=Source-archive-test \
    -c user.email=source-archive-test@example.invalid commit -qm 'Archived source baseline for offline test'

# shellcheck source=scripts/lib.sh
. "$project/scripts/lib.sh"
check_fdtget
apply_patch_series "$OPENWRT_SOURCE_DIR" "$project/openwrt/patches"
for patch in "$project"/kernel-patches/*.patch; do
    install -m 0644 "$patch" "$OPENWRT_SOURCE_DIR/target/linux/mvebu/patches-6.12/"
    git -C "$OPENWRT_SOURCE_DIR" add "target/linux/mvebu/patches-6.12/$(basename "$patch")"
done
generate_feeds_conf "$project/feeds.lock" "$OPENWRT_SOURCE_DIR/feeds.conf"
# -i indexes the already restored feeds; it does not update or fetch them.
(cd "$OPENWRT_SOURCE_DIR"; ./scripts/feeds update -i; ./scripts/feeds install -a)
"$project/scripts/install-public-files.sh"
cp "$work/bundle/openwrt.config" "$OPENWRT_SOURCE_DIR/.config"
make -C "$OPENWRT_SOURCE_DIR" defconfig
cmp "$work/bundle/openwrt.config" "$OPENWRT_SOURCE_DIR/.config"

# No restored toolchain, object files or compiler cache. Every build input must
# already exist in the verified downloads or archived source trees.
sh "$script_dir/make-with-diagnostics.sh" -C "$OPENWRT_SOURCE_DIR" -j"$JOBS" DL_DIR="$work/downloads/dl" download
sh "$script_dir/make-with-diagnostics.sh" -C "$OPENWRT_SOURCE_DIR" -j"$JOBS" DL_DIR="$work/downloads/dl"
kernel_tree=$(find "$OPENWRT_SOURCE_DIR/build_dir/target-"* -maxdepth 2 -type d -name 'linux-6.12.*' -print)
[ "$(printf '%s\n' "$kernel_tree" | wc -l)" -eq 1 ] && [ -d "$kernel_tree" ]
python3 "$script_dir/compare-kernel-config.py" "$work/bundle/linux.config" "$kernel_tree/.config" \
    --source-root "$OPENWRT_SOURCE_DIR"
python3 "$project/tests/check-atags.py" "$kernel_tree"
"$project/scripts/package-buffalo.sh"
python3 - "$work" <<'PY'
import hashlib, json, pathlib, sys
work = pathlib.Path(sys.argv[1])
manifest = dict(line.split('=', 1) for line in (work/'bundle/build.manifest').read_text().splitlines())
products = {}
for name in ('uImage.buffalo', 'initrd.buffalo', 'packages.manifest'):
    actual = hashlib.sha256((work/'artifacts'/name).read_bytes()).hexdigest()
    expected = manifest[f'ARTIFACT_SHA256[{name}]']
    products[name] = {'sha256': actual, 'expected_sha256': expected, 'match': actual == expected}
report = {
    'source_zip_sha256': json.loads((work/'RESTORED.json').read_text())['source_zip_sha256'],
    'source_project_commit': manifest['REPOSITORY_COMMIT'],
    'network_isolated': True, 'compiler_cache_used': False,
    'offline_compile_and_packaging_passed': True,
    'products': products, 'all_products_match': all(p['match'] for p in products.values()),
    'license_review_complete': False, 'firmware_distribution_authorized': False,
}
(work/'offline-result.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
if not report['all_products_match']:
    raise SystemExit('offline build completed but product hashes differ; review required')
PY
