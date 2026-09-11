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

A [configuration-only Buildbot experiment](buildbot-config-20260911.md) records
which unrelated defaults must be disabled and which other behaviors change.
It has not changed the canonical firmware configuration.

The next comparison must still determine all differing files and whether there
are additional kernel or container-header differences. Neither successful
compilation nor matching filenames is a reproducibility result.

## File-level comparison

[Diagnostic run 34577568680](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34577568680)
produced two complete firmware evidence sets from commit
`35df90cd45bae093b94009b5cd40c635ba3ff058`. Both evidence ZIP hashes and every
member checksum were verified:

| Copy | Evidence artifact | ZIP SHA-256 |
| --- | --- | --- |
| A | 10192848525 | 41c4463677f0d7d59a4431c79daf00c02d885645eeb8f18878c408e1ffd67c50 |
| B | 10192981817 | 19ca7bb60ddf43a1b0548c8ea51d89f576cb9ae0f142a321a241cca6254e1e79 |

Both inventories contain 996 entries. Exactly three differ:

| Rootfs path | A size | B size | Difference |
| --- | ---: | ---: | --- |
| etc/apk/keys/public-key.pem | 178 | 178 | Content hash |
| lib/apk/db/installed | 101828 | 101828 | Content hash |
| lib/apk/db/scripts.tar.gz | 11032 | 11034 | Content hash and size |

The official `etc/apk/keys/openwrt-25.12.pem` is identical. All other recorded
file contents, sizes, modes, types and symlink targets agree.
A's uImage hash is
`5d85854f0e05800058dd17c5469e6ae7f595c870dcfd6842ecfc5e0e00f15d08`;
B's is
`45e8c2f1ba632bee4cfc413463857f82d1d19f553c6d251b7b46173cb842b74d`.

APK 3.0.5's `src/database.c`, function `apk_db_scriptdb_write`, includes the
package hash in script archive entry names. A varying base-files package can
therefore affect the script database as well as the installed-package database.
The observed differences are consistent with that mechanism; the inventories
alone do not prove there are no additional differences inside those databases.

## Fix under test

The canonical config now enables the reviewed BUILDBOT mode, explicitly keeps
package signing and verification enabled, pins the kernel build identity and
disables unrelated default build products and the owut upgrade client.
Its resolved config is byte-identical to the earlier
[configuration experiment](buildbot-config-20260911.md), including the same
package selections. It does not replace trusted keys with a shared private key.

The next independent comparison must establish whether this removes all product
differences. The failed comparisons remain evidence; none is reclassified as
a successful reproducible build.
