#!/bin/sh
# SPDX-License-Identifier: MIT

set -eu
REPO_ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
# shellcheck source=scripts/lib.sh
. "$REPO_ROOT/scripts/lib.sh"

TEST_TMP=$(mktemp -d "${TMPDIR:-/tmp}/ls420d-tests.XXXXXX")
trap 'rm -rf "$TEST_TMP"' EXIT HUP INT TERM
pass=0

ok() {
    pass=$((pass + 1))
    printf 'ok %d - %s\n' "$pass" "$1"
}

expect_failure() {
    description=$1
    shift
    if ("$@") >/dev/null 2>&1; then
        fail "expected failure: $description"
    fi
    ok "$description"
}

load_openwrt_lock "$REPO_ROOT/openwrt.lock"
[ "$OPENWRT_COMMIT" = f0a60eee2fe051741c643ea6118718aae1ef17fb ]
ok 'versioned OpenWrt lock parses without shell evaluation'

cp "$REPO_ROOT/openwrt.lock" "$TEST_TMP/duplicate.lock"
printf 'OPENWRT_TAG=v25.12.5\n' >> "$TEST_TMP/duplicate.lock"
expect_failure 'duplicate lock keys are rejected' load_openwrt_lock "$TEST_TMP/duplicate.lock"

cp "$REPO_ROOT/openwrt.lock" "$TEST_TMP/unknown.lock"
printf 'SURPRISE=value\n' >> "$TEST_TMP/unknown.lock"
expect_failure 'unknown lock keys are rejected' load_openwrt_lock "$TEST_TMP/unknown.lock"

sed '/^OPENWRT_TAG_OBJECT=/d' "$REPO_ROOT/openwrt.lock" > "$TEST_TMP/missing.lock"
expect_failure 'missing lock keys are rejected' load_openwrt_lock "$TEST_TMP/missing.lock"

marker=$TEST_TMP/lock-was-executed
sed "s#^OPENWRT_VERSION=.*#OPENWRT_VERSION=\$(touch $marker)#" \
    "$REPO_ROOT/openwrt.lock" > "$TEST_TMP/injection.lock"
expect_failure 'shell syntax in lock values is rejected' load_openwrt_lock "$TEST_TMP/injection.lock"
[ ! -e "$marker" ] || fail 'lock file content was executed'

validate_feeds_lock "$REPO_ROOT/feeds.lock"
generate_feeds_conf "$REPO_ROOT/feeds.lock" "$TEST_TMP/feeds.conf"
[ "$(wc -l < "$TEST_TMP/feeds.conf" | tr -d ' ')" -eq 5 ]
[ "$(sed -n '1p' "$TEST_TMP/feeds.conf")" = \
  'src-git packages https://github.com/openwrt/packages.git^5caa62e0bc9f7fb9b0c12a23267bceb7724214dd' ]
ok 'feed lock produces exact commit-qualified feed configuration'

awk '1; /^packages\|/ { print }' "$REPO_ROOT/feeds.lock" > "$TEST_TMP/duplicate-feeds.lock"
expect_failure 'duplicate feeds are rejected' validate_feeds_lock "$TEST_TMP/duplicate-feeds.lock"

mkdir -p "$TEST_TMP/unmanaged/.git" "$TEST_TMP/managed/.git"
expect_failure 'existing unmanaged source checkout is rejected' assert_managed_source "$TEST_TMP/unmanaged"
: > "$TEST_TMP/managed/.git/ls420d-managed"
assert_managed_source "$TEST_TMP/managed"
ok 'only a checkout carrying the script ownership marker is accepted'

patch_source=$TEST_TMP/patch-source
patches=$TEST_TMP/patches
mkdir -p "$patch_source" "$patches"
git -C "$patch_source" init -q
git -C "$patch_source" config user.name Fixture
git -C "$patch_source" config user.email fixture@example.invalid
printf 'before\n' > "$patch_source/board.txt"
git -C "$patch_source" add board.txt
git -C "$patch_source" commit -qm base
printf 'after\n' > "$patch_source/board.txt"
git -C "$patch_source" diff --binary > "$patches/001-board.patch"
git -C "$patch_source" checkout -q -- board.txt
printf '001-board.patch\n' > "$patches/series"
apply_patch_series "$patch_source" "$patches"
first_patch_identity=$(git -C "$patch_source" diff --cached | sha256sum | awk '{print $1}')
first_head=$(git -C "$patch_source" rev-parse HEAD)
git -C "$patch_source" reset -q --hard HEAD
apply_patch_series "$patch_source" "$patches"
second_patch_identity=$(git -C "$patch_source" diff --cached | sha256sum | awk '{print $1}')
[ "$first_patch_identity" = "$second_patch_identity" ]
[ "$first_head" = "$(git -C "$patch_source" rev-parse HEAD)" ]
ok 'non-empty patch series is deterministic and creates no commit'

git check-ignore -q artifacts/firmware.bin
git check-ignore -q artifacts/raw.log
if git check-ignore -q artifacts/build.manifest; then fail 'curated manifest is ignored'; fi
if git check-ignore -q artifacts/build.sha256; then fail 'curated checksum is ignored'; fi
git check-ignore -q build/artifacts/build.manifest
ok 'ignore rules retain curated text evidence but exclude firmware and raw logs'

manifest_root=$TEST_TMP/repository
mkdir -p "$manifest_root/scripts" "$manifest_root/openwrt/patches" \
    "$manifest_root/source/bin/targets/mvebu/cortexa9" \
    "$manifest_root/source/staging_dir/toolchain-test/bin" "$manifest_root/out"
cp "$REPO_ROOT/openwrt.lock" "$REPO_ROOT/feeds.lock" "$manifest_root/"
cp "$REPO_ROOT/openwrt/patches/series" "$manifest_root/openwrt/patches/"
cp "$REPO_ROOT/openwrt/patches/"*.patch "$manifest_root/openwrt/patches/"
cp "$REPO_ROOT/scripts/lib.sh" "$REPO_ROOT/scripts/write-manifest.sh" "$manifest_root/scripts/"
printf 'CONFIG_TARGET_TEST=y\n' > "$manifest_root/source/.config"
printf 'build metadata\n' > "$manifest_root/source/bin/targets/mvebu/cortexa9/config.buildinfo"
printf 'kernel\n' > "$manifest_root/out/uImage.buffalo"
printf 'ramdisk\n' > "$manifest_root/out/initrd.buffalo"
printf 'packages\n' > "$manifest_root/out/packages.manifest"
for evidence in rootfs-inventory.json upstream-delta.patch public-files.sha256 kernel-patches.sha256; do
    printf 'fixture evidence\n' > "$manifest_root/out/$evidence"
done
cat > "$manifest_root/source/staging_dir/toolchain-test/bin/arm-openwrt-linux-gcc" <<'EOF'
#!/bin/sh
printf 'arm-openwrt-linux-muslgnueabi-gcc 14.3.0\n'
EOF
chmod 0755 "$manifest_root/source/staging_dir/toolchain-test/bin/arm-openwrt-linux-gcc"
git -C "$manifest_root" init -q
git -C "$manifest_root" config user.name Test
git -C "$manifest_root" config user.email test@example.invalid
git -C "$manifest_root" add .
git -C "$manifest_root" commit -qm fixture
REPO_ROOT=$manifest_root OPENWRT_SOURCE_DIR=$manifest_root/source ARTIFACT_DIR=$manifest_root/out \
SOURCE_DATE_EPOCH=123456789 "$manifest_root/scripts/write-manifest.sh" >/dev/null
cp "$manifest_root/out/build.manifest" "$TEST_TMP/first.manifest"
REPO_ROOT=$manifest_root OPENWRT_SOURCE_DIR=$manifest_root/source ARTIFACT_DIR=$manifest_root/out \
SOURCE_DATE_EPOCH=123456789 "$manifest_root/scripts/write-manifest.sh" >/dev/null
cmp "$TEST_TMP/first.manifest" "$manifest_root/out/build.manifest"
[ "$(grep -c '^ARTIFACT_SHA256\[' "$manifest_root/out/build.manifest")" -eq 7 ]
grep -q '^CONFIG_SHA256=' "$manifest_root/out/build.manifest"
grep -q '^TARGET_COMPILER=arm-openwrt-linux-muslgnueabi-gcc 14.3.0$' \
    "$manifest_root/out/build.manifest"
grep -q '^PATCH_SERIES_SHA256=' "$manifest_root/out/build.manifest"
grep -q '^BUILDINFO_SHA256\[mvebu/cortexa9/config.buildinfo\]=' "$manifest_root/out/build.manifest"
if grep -q "$TEST_TMP" "$manifest_root/out/build.manifest"; then
    fail 'manifest contains an absolute temporary path'
fi
ok 'manifest path is exercised and output is deterministic and path-independent'

mv "$manifest_root/out/initrd.buffalo" "$manifest_root/out/not-initrd.buffalo"
expect_failure 'manifest fails when an exact Buffalo artifact is missing' env \
    REPO_ROOT="$manifest_root" OPENWRT_SOURCE_DIR="$manifest_root/source" \
    ARTIFACT_DIR="$manifest_root/out" SOURCE_DATE_EPOCH=123456789 \
    "$manifest_root/scripts/write-manifest.sh"

[ -s "$REPO_ROOT/config/ls420d.config" ]
grep -q '^CONFIG_TARGET_mvebu_cortexa9_DEVICE_buffalo_ls420d=y$' \
    "$REPO_ROOT/config/ls420d.config"
grep -q '^CONFIG_TARGET_ROOTFS_INITRAMFS=y$' "$REPO_ROOT/config/ls420d.config"
if grep -RIE 'BEGIN (OPENSSH|RSA|EC|DSA) PRIVATE KEY|([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}|/mnt/[a-z]/Users/|[A-Za-z]:[\\]Users[\\]' \
    "$REPO_ROOT/config" "$REPO_ROOT/openwrt"; then
    fail 'public build inputs contain deployment identity or private key material'
fi
ok 'public LS420D build inputs are RAM-only and deployment-neutral'

grep -q '^# CONFIG_PACKAGE_uboot-envtools is not set$' "$REPO_ROOT/config/ls420d.config"
if grep -q 'uboot-envtools' "$REPO_ROOT/openwrt/patches/"*.patch; then
    fail 'patch series configures U-Boot environment access on a RAM-only device'
fi
ok 'generic build carries no write path into the SPI NOR bootloader environment'

printf '1..%d\n' "$pass"
