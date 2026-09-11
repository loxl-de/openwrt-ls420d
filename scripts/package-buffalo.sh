#!/bin/sh
# SPDX-License-Identifier: MIT

set -eu
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd)
# shellcheck source=scripts/lib.sh
. "$SCRIPT_DIR/lib.sh"

SOURCE_DIR=${OPENWRT_SOURCE_DIR:-$REPO_ROOT/openwrt-src}
ARTIFACT_DIR=${ARTIFACT_DIR:-$REPO_ROOT/build/artifacts}
: "${SOURCE_DATE_EPOCH:?SOURCE_DATE_EPOCH must be exported before packaging}"

TARGET_DIR=$SOURCE_DIR/bin/targets/mvebu/cortexa9
MKIMAGE=${MKIMAGE:-$SOURCE_DIR/staging_dir/host/bin/mkimage}
FDTGET=${FDTGET:-$SOURCE_DIR/staging_dir/host/bin/fdtget}

kernel_count=$(find "$TARGET_DIR" -maxdepth 1 -type f \
    -name '*-buffalo_ls420d-initramfs-kernel.bin' -print | wc -l | tr -d ' ')
[ "$kernel_count" -eq 1 ] ||
    fail 'expected exactly one non-empty LS420D initramfs kernel'
kernel=$(find "$TARGET_DIR" -maxdepth 1 -type f \
    -name '*-buffalo_ls420d-initramfs-kernel.bin' -print)
[ -s "$kernel" ] || fail 'LS420D initramfs kernel is empty'

package_count=$(find "$TARGET_DIR" -maxdepth 1 -type f \
    -name '*-buffalo_ls420d.manifest' -print | wc -l | tr -d ' ')
[ "$package_count" -eq 1 ] ||
    fail 'expected exactly one non-empty LS420D package manifest'
package_manifest=$(find "$TARGET_DIR" -maxdepth 1 -type f \
    -name '*-buffalo_ls420d.manifest' -print)
[ -s "$package_manifest" ] || fail 'LS420D package manifest is empty'

[ -x "$MKIMAGE" ] || fail "OpenWrt mkimage not found: $MKIMAGE"
[ -x "$FDTGET" ] || fail "OpenWrt fdtget not found: $FDTGET"

dtb_count=$(find "$SOURCE_DIR/build_dir" -type f \
    -name 'image-armada-370-buffalo-ls420d.dtb' -print | wc -l | tr -d ' ')
[ "$dtb_count" -eq 1 ] || fail 'expected exactly one compiled LS420D DTB'
dtb=$(find "$SOURCE_DIR/build_dir" -type f \
    -name 'image-armada-370-buffalo-ls420d.dtb' -print)

compatible=$("$FDTGET" "$dtb" / compatible)
primary_compatible=$(printf '%s\n' "$compatible" | awk '{ print $1 }')
[ "$primary_compatible" = 'buffalo,ls420d' ] ||
    fail 'compiled DTB has the wrong primary identity'
case " $compatible " in
    *' buffalo,ls421de '*) fail 'compiled DTB retains the temporary LS421DE fallback' ;;
esac

for node in \
    /soc/pcie@82000000 \
    /soc/internal-regs/nand-controller@d0000 \
    /soc/internal-regs/mvsdio@d4000
do
    [ "$("$FDTGET" "$dtb" "$node" status)" = disabled ] ||
        fail "dangerous inherited node is not disabled: $node"
done

kernel_size=$(wc -c < "$kernel" | tr -d ' ')
# Buffalo loads the kernel at 0x01200000 and the companion initrd at
# 0x02600000. Keep the embedded-initramfs uImage inside that 20 MiB gap.
[ "$kernel_size" -lt 20971520 ] ||
    fail 'LS420D initramfs kernel overlaps the Buffalo initrd load address'

# The decompressed kernel starts at 0x00008000 and must also stay below the
# initrd load address, including .bss and the relocated decompressor.
kernel_tree=$(find "$SOURCE_DIR/build_dir/target-"* -maxdepth 2 -type d -name 'linux-6.12.*' -print)
[ "$(printf '%s\n' "$kernel_tree" | grep -c .)" -eq 1 ] || fail 'expected exactly one prepared Linux tree'
[ -s "$kernel_tree/vmlinux" ] || fail 'uncompressed kernel ELF image missing'
python3 "$SCRIPT_DIR/check-kernel-footprint.py" "$kernel_tree/vmlinux" "$kernel"

mkdir -p "$ARTIFACT_DIR"
install -m 0644 "$kernel" "$ARTIFACT_DIR/uImage.buffalo"
install -m 0644 "$package_manifest" "$ARTIFACT_DIR/packages.manifest"

# A real, anonymous CPIO companion replaces the former invalid gzip dummy.
[ ! -e "$ARTIFACT_DIR/initrd.buffalo" ] || fail 'artifact directory is not fresh'
python3 "$SCRIPT_DIR/make_initrd.py" --example --output "$ARTIFACT_DIR/initrd.buffalo"
root_count=$(find "$SOURCE_DIR/build_dir" -maxdepth 2 -type d -name root-mvebu | wc -l | tr -d ' ')
[ "$root_count" -eq 1 ] || fail 'expected exactly one built-in rootfs'
rootfs=$(find "$SOURCE_DIR/build_dir" -maxdepth 2 -type d -name root-mvebu)
python3 "$SCRIPT_DIR/audit-rootfs.py" "$rootfs" "$ARTIFACT_DIR/rootfs-inventory.json"
git -C "$SOURCE_DIR" diff --binary HEAD > "$ARTIFACT_DIR/upstream-delta.patch"
(cd "$REPO_ROOT/openwrt/files"; find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum) > "$ARTIFACT_DIR/public-files.sha256"
(cd "$REPO_ROOT/kernel-patches"; sha256sum ./*.patch) > "$ARTIFACT_DIR/kernel-patches.sha256"
"$MKIMAGE" -l "$ARTIFACT_DIR/uImage.buffalo" >/dev/null
"$MKIMAGE" -l "$ARTIFACT_DIR/initrd.buffalo" >/dev/null
printf 'Packaged generic kernel and SSH-disabled example companion in %s\n' "$ARTIFACT_DIR"
