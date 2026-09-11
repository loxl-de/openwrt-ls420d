# First independent build comparison

[Run 34569475342, attempt 2](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34569475342)
completed both firmware builds successfully. Their product comparison failed.
Both used project commit `b11688ac8765bb76f40c6507814e3e80242109ae`.

The differing primary product is `uImage.buffalo`:

- Build A: `b327448d628e469bfab0b37d39ee9b9ecf734d09eaa4bab9737f3133620f3ba1`
- Build B: `b4ef36f325c125df3354f21b8dc3d72cb2773d0beac2b7a48aa0e888e967a93b`

The example companion, package manifest, public overlay checksums and patch
checksums agree. The build manifests differ only in the kernel-image hash.
The source/configuration buildinfo hashes also agree. Both evidence ZIP digests
and every member in their EVIDENCE-SHA256SUMS inventories were verified.

The old rootfs inventory listed paths and types only. Its agreement does not
establish equal file contents. The inventory now also records regular-file
SHA-256, size and mode, and symlink targets without following them. Host-side
timestamps are excluded because Linux normalizes initramfs timestamps here.
This change collects diagnostics; it does not alter the firmware or waive the
comparison requirement.

The pinned OpenWrt `package/Makefile` generates an APK signing key during each
build. `package/base-files/Makefile` copies its public half into `/etc/apk/keys`
unless CONFIG_BUILDBOT is enabled. This is a concrete source of varying rootfs
content that the next file-level comparison can identify. Signature checking
and trusted package keys have not been weakened or replaced.

The next comparison must still determine all differing files and whether there
are additional kernel or container-header differences. Neither successful
compilation nor matching filenames is a reproducibility result.
