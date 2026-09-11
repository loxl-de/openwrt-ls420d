# Runtime source notice review, 2026-09-11

This review uses the verified bundle described in
[source-review-25.12.5.md](source-review-25.12.5.md). It records component
identification and inspected notices, not distribution approval. No hardware
or firmware configuration changed.

## Resolve the common toolchain recipe

OpenWrt's `package/libs/toolchain/Makefile` declares
`GPL-3.0-with-GCC-exception` for the whole recipe. Six installed packages inherit
that metadata, but it does not describe six identical runtime components.

The resolved configuration selects `CONFIG_USE_MUSL=y`, `CONFIG_LIBC="musl"`
and GCC 14.3.0, with no external toolchain.

| Installed package | Source and installation rule |
| --- | --- |
| libc 1.2.5-r5 | musl 1.2.5; installs musl's dynamic loader and libc |
| libpthread 1.2.5-r5 | The musl branch does not copy a separate pthread library |
| librt 1.2.5-r5 | The musl branch does not copy a separate realtime library |
| libgcc1 14.3.0-r5 | GCC 14.3.0; installs libgcc_s.so.* |
| libatomic1 14.3.0-r5 | GCC 14.3.0; installs libatomic.so.* |
| libstdcpp6 14.3.0-r5 | GCC 14.3.0; installs libstdc++.so.* |

These are recipe-level mappings. The final release review must also check the
installed files and preserve notices for any linked third-party code.

## musl

The complete `musl-1.2.5/COPYRIGHT` was read. It gives the overall MIT license,
lists contributors and identifies third-party components with their own notices.
The file's SHA-256 is
`f9bc4423732350eb0b3f7ed7e91d530298476f8fec0c6c427a1c04ade22655af`.

The following source headers were checked separately:

- `src/string/arm/memcpy.S`: Android Open Source Project copyright,
  two-clause BSD terms, including binary-distribution notice requirements.
- `src/regex/regcomp.c` and `src/regex/tre.h`: Ville Laurikari copyright
  and two-clause BSD terms. Their notices give 2001–2009, whereas the overview
  says 2001–2008; retain the actual file notices rather than rewriting dates.
- `src/crypt/crypt_des.c`: David Burren and Solar Designer copyrights,
  three-clause BSD terms.
- `src/crypt/crypt_blowfish.c`: Solar Designer's public-domain statement
  and fallback permissive terms.
- `src/stdlib/qsort.c`: Valentin Ochs copyright and MIT-style terms.
- `src/math/exp.c`: Arm Limited copyright and MIT SPDX identifier.

This is not an exhaustive audit of musl's math, complex or architecture-specific
files. A final notice collection must preserve those applicable notices too.
The recipe's inherited GCC declaration must not replace musl's own terms.

## GCC runtimes

The complete `gcc-14.3.0/COPYING.RUNTIME` was read. It is GCC Runtime Library
Exception 3.1 and explicitly applies to files bearing the corresponding notice.
Its presence is not a blanket exception for all GCC sources.

Explicit GPL version 3-or-later and runtime-exception notices were confirmed in:

- `libgcc/libgcc2.c` and `libgcc/config/arm/lib1funcs.S`;
- `libatomic/Makefile.am`;
- `libstdc++-v3/src/c++11/chrono.cc`.

In contrast, `libstdc++-v3/Makefile.am` contains a GPL version 3-or-later
notice without that exception. Build scripts and runtime files must not be
classified solely from their directory name.

The archive includes both accompanying texts:

| File | SHA-256 |
| --- | --- |
| COPYING3 | 8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903 |
| COPYING.RUNTIME | 9d6b43ce4d8de0c878bf16b54d8e7a10d9bd42b75178153e3af6a815bdc90f74 |

The source archives preserve the files in full. This inspection has not yet
produced the complete binary-accompanying notice collection or reviewed every
selected runtime source file. The [distribution gate](../distribution.md)
remains closed.

## Dropbear 2025.89

The complete top-level `LICENSE`, `libtomcrypt/LICENSE` and
`libtommath/LICENSE` were read. OpenWrt enables `--enable-bundled-libtom`,
so the bundled libraries' notices belong in this review.

The top-level license identifies the predominantly MIT-licensed implementation,
OpenSSH-derived files, PuTTY-derived key import code and the modified TweetNaCl
component. The full headers of `src/atomicio.c` and `src/loginrec.c` contain
two-clause BSD terms. `src/sshpty.c` preserves Tatu Ylonen's permission notice
and its conditions on marking derived versions and naming incompatible versions.

LibTomCrypt offers public-domain or WTFPL version 2 terms. LibTomMath carries
its public-domain dedication and disclaimer. The inherited OpenWrt `MIT`
label must not replace these notices.

| Archive-relative file | SHA-256 |
| --- | --- |
| LICENSE | a99ce657d790b761c132ee7e0de18edb437ae6361e536d991c6a12f36e770445 |
| libtomcrypt/LICENSE | 8f196cb13afd271f5e267fd29543fc454596382ad580e7592709492843996ac8 |
| libtommath/LICENSE | 2fa64b163659f41965c9815882a8296d3d03ff546b76153e11445f9bdecf955a |

## e2fsprogs 1.47.3

The component overview at the start of `NOTICE` distinguishes the tools from
their libraries. The complete license texts later in that file were not
reviewed in this pass.

| Installed package | Source component and inspected notice |
| --- | --- |
| libe2p2 | lib/e2p; feature.c states GNU Library General Public License version 2 |
| libext2fs2 | lib/ext2fs; openfs.c states GNU Library General Public License version 2 |
| libcomerr0 | lib/et; com_err.c carries the MIT Student Information Processing Board permission notice |
| libss2 | lib/ss; data.c carries the MIT Student Information Processing Board permission notice |

The last two notices restrict use of the institution's names in advertising
without written permission. Preserve their actual wording rather than
substituting the standard MIT text. OpenWrt's common `GPL-2.0` recipe label
does not capture these distinctions. The selected `libuuid1` comes from
util-linux, not this archive; e2fsprogs' lib/uuid notice is not its source mapping.

## PPP 2.5.2

The complete `COPYING` and `LICENSE.BSD` were read. `COPYING` explicitly
directs readers to individual file notices and distinguishes BSD-style daemon
code from GPL plugins. `LICENSE.BSD` contains a three-clause Berkeley notice;
it is not a replacement for every other source notice.

The complete copyright header of `pppd/main.c` includes Carnegie Mellon
University's four-clause notice and Paul Mackerras' two-clause notice. The former
requires retaining its acknowledgment; a final notice collection must include
the original text.

OpenWrt installs `pppoe.so` in the selected `ppp-mod-pppoe` package.
Its `pppd/plugins/pppoe/plugin.c` header states GPL version 2 or later and
names Roaring Penguin Software Inc., Michal Ostrowski and Jamal Hadi Salim.
The inherited `BSD-4-Clause` package metadata therefore does not describe
this plugin's entire source. Other plugin source headers still need to be
included in the notice collection.

These findings identify specific notices that a package-label-only report
would miss. They do not change upstream license declarations, approve
distribution, or claim that every compiled file has been reviewed.

## util-linux 2.41.5

The verified source bundle from comparison 34585193428, copy B, selects six
packages from this recipe, all at version 2.41.5-r1. The source archive hash is
`f586e35d320ff537aab3ffeca37e9ecd482ccbe013590db4429a414d8aa6a728`.

| Installed package | Component and recipe declaration |
| --- | --- |
| libblkid1 | libblkid; LGPL-2.1-or-later |
| libmount1 | libmount; LGPL-2.1-or-later |
| libsmartcols1 | libsmartcols; LGPL-2.1-or-later |
| libuuid1 | libuuid; BSD-3-Clause |
| lsblk | misc-utils/lsblk.c; GPL-2.0-or-later |
| partx-utils | partx, addpart and delpart; GPL-2.0-or-later |

The four library `COPYING` notices were read completely. They point to the
corresponding license texts under `Documentation/licenses`; the three LGPL
notices explicitly select version 2.1 or later. The full copyright headers of
`libblkid/src/cache.c`, `libmount/src/context.c`,
`libsmartcols/src/table.c` and `libuuid/src/gen_uuid.c` were also read.
The declarations and these component notices agree; the generic COPYING file
at the archive root must not replace the library notices.

The libuuid Meson recipe includes `lib/randutils.c`, `lib/md5.c` and
`lib/sha1.c`. Their headers were inspected: randutils identifies BSD-3-Clause,
while the MD5 and SHA-1 implementations carry public-domain statements naming
Colin Plumb and Steve Reid. Preserve those statements with the component
attribution rather than presenting all three files as solely BSD-licensed.

The headers of lsblk, partx, addpart and delpart state GPL version 2 or later.
Although the archive also contains resizepart, OpenWrt's selected partx-utils
installation rule does not install it.

| License text under Documentation/licenses | SHA-256 |
| --- | --- |
| COPYING.BSD-3-Clause | 9b718a9460fed5952466421235bc79eb49d4e9eacc920d7a9dd6285ab8fd6c6d |
| COPYING.LGPL-2.1-or-later | dc626520dcd53a22f727af3ee42c770e56c97a64fe3adb063799d8ab032fe551 |
| COPYING.GPL-2.0-or-later | 8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643 |

All three texts were found and hashed; the BSD text was read completely in this
pass. This review resolves the selected package mapping and the listed notices.
It does not claim an exhaustive review of shared helper sources or replace
the remaining notice collection.

## Storage tools

The verified source bundle and rootfs inventory from comparison 34585193428,
copy B, contain btrfs-progs 6.11-r3, hdparm 9.65-r2 and smartmontools 7.5-r1.
The following findings cover their installation rules and the notices named
below, not every compiled source file.

### btrfs-progs

The recipe declares GPL-2.0-only and lists only the top-level `COPYING`.
Its installation rule also copies `libbtrfsutil.so*`. The rootfs inventory
confirms both `libbtrfs.so.0.1.4` and `libbtrfsutil.so.1.3.2`, alongside
the command-line tools.

The complete copyright headers of `libbtrfsutil/filesystem.c` and
`libbtrfsutil/btrfsutil.h` state LGPL version 2.1 or later and name Facebook.
The library has its own `libbtrfsutil/COPYING`, whose heading identifies
LGPL 2.1. A notice collection must retain that component's terms rather than
apply the recipe's GPL-only label to everything it installs.

### hdparm

The recipe declares BSD-2-Clause and installs `/sbin/hdparm`.
The complete `LICENSE.TXT` was read. It contains Mark Lord's short
BSD-style permission notice, not the standard two-clause BSD text. Preserve
its actual wording and attribution.

The source Makefile links `apt.o` into hdparm. Both the top-level notice
and the inspected `apt.c` header name Jan Friesse and offer GPL version 2
or BSD-style terms for that file. Its notice cannot be omitted on the
assumption that apt.c is an unbuilt extra.

### smartmontools

The selected package installs `/usr/sbin/smartctl`; the verified manifest
does not select the separate smartd or smartmontools-drivedb packages.
The rootfs inventory confirms smartctl and contains neither a smartd program
nor a separate drivedb file. This does not imply that smartctl lacks a compiled-in
drive database.

The complete copyright header of `smartctl.cpp` names Bruce Allen,
Christian Franke and Michael Cornwell and states GPL-2.0-or-later, consistent
with the recipe. Other linked source notices remain part of the pending review.

### Recorded license-file hashes

| Archive | Archive-relative file | SHA-256 |
| --- | --- | --- |
| btrfs-progs-v6.11.tar.xz | COPYING | 0d5bf346df9e635a29dcdddf832dc5b002ca6cdc1c5c9c6c567d2a61bb0c5c15 |
| btrfs-progs-v6.11.tar.xz | libbtrfsutil/COPYING | dc626520dcd53a22f727af3ee42c770e56c97a64fe3adb063799d8ab032fe551 |
| hdparm-9.65.tar.gz | LICENSE.TXT | eae572b06d2733f5c65fbe81680ce2b8a109afee2bdd1a161343c772af0e82e1 |
| smartmontools-7.5.tar.gz | COPYING | 8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643 |

All four files were found and hashed. Only hdparm's complete license text and
the source headers identified above were read in this pass; the GPL and LGPL
texts were not read in full. These findings do not open the distribution gate.

## BusyBox 1.37.0-r6

The top-level `LICENSE` explicitly restricts distribution of this BusyBox
version and derived versions to GPL version 2. Its version-selection preface
was read; the following full GPL text was not read in this pass.

The resolved configuration uses the default applet selection and enables ash.
Both the opening header and the complete retained Berkeley notice at the end
of `shell/ash.c` were read. The file names Kenneth Almquist, the Regents of
the University of California and Herbert Xu. Its retained three-clause BSD
notice requires attribution in materials accompanying binary distribution.
Keep that notice as well as BusyBox's top-level license.

The recipe also lists `archival/libarchive/bz/LICENSE`. That complete
bzip2 1.0.4 notice was read; it names Julian R Seward and includes conditions
on source attribution, altered sources and endorsement. Listing it in the
recipe does not establish that the bzip2 applet is in this image.
The resolved configuration disables BZIP2, BUNZIP2, BZCAT, seamless bzip2,
bzip2 decompression, unzip-bzip2 and compressed usage. The inspected
`archival/libarchive/Kbuild.src` selects the decompression helper through
those feature switches. Preserve the notice in the source archive; do not
report the applet as enabled merely because its license file exists.

## ethtool 6.15-r1

The selected package is `ethtool`, not `ethtool-full`. Its tiny variant
disables Netlink and pretty register dumps and installs `/usr/sbin/ethtool`.
No package selection or runtime behavior was changed during this review.

The complete short `LICENSE` identifies GPL version 2 and refers to
`COPYING`. The source Makefile includes JSON output helpers even without
the full variant. Inspected headers show:

- `json_writer.c` offers GPL-2.0 or BSD-2-Clause and names Stephen Hemminger.
- `json_print.c` states GPL version 2 or later and names Julien Fortin.
- `uapi/linux/ethtool.h` carries GPL-2.0 with Linux-syscall-note.

These file-specific notices do not replace the top-level distribution terms.
The complete initial attribution block of `ethtool.c` was also read.
The review does not cover every source or UAPI header in its Makefile.

| Archive | License file | SHA-256 |
| --- | --- | --- |
| busybox-1.37.0.tar.bz2 | LICENSE | bbfc9843646d483c334664f651c208b9839626891d8f17604db2146962f43548 |
| busybox-1.37.0.tar.bz2 | archival/libarchive/bz/LICENSE | b5a136ed67798e51fe2e0ca0b2a21cb01b904ff0c9f7d563a6292e276607e58f |
| ethtool-6.15.tar.xz | LICENSE | 5d632934396f90c82dfebe3c9512648bbb6333b406113d0cd331b0e0aa2d34a1 |
| ethtool-6.15.tar.xz | COPYING | 8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643 |

These files were found and hashed in the same verified B source bundle.
The complete GPL text in ethtool's COPYING was not read in this pass.

## Runtime compression libraries

The verified B manifest selects `zlib 1.3.1-r1` and `liblzo2 2.10-r5`.
The rootfs inventory confirms `usr/lib/libz.so.1.3.1` and
`usr/lib/liblzo2.so.2.0.0`. OpenWrt names the latter recipe `liblzo`;
its ABI suffix accounts for the installed package name `liblzo2`.

The full zlib `LICENSE` and the complete copyright/permission header in
`zlib.h` were read. Both use the zlib permission terms, but the top-level
file gives 1995–2022 while the header gives 1995–2024 for Jean-loup Gailly
and Mark Adler. Preserve the actual notices rather than harmonizing the dates.

OpenWrt also ships ARM optimization patches for zlib. The inspected headers
in patches 002 and 003 name Mark Adler for the adapted inflate files and
ARM, Inc. for `chunkcopy.h`; all refer to the notice in `zlib.h`.
Patch 004 selects these sources conditionally through CMake's ARMv8 option.
These patches must accompany the source offer even if a particular target
does not compile that branch. This inspection did not establish the resolved
per-package CMake cache value.

The LZO recipe declares GPL-2.0-or-later and installs shared `liblzo2.so.*`.
Complete headers in `src/lzo1x_1.c` and `include/lzo/lzoconf.h`
confirm version 2 or later and name Markus Franz Xaver Johannes Oberhumer.
The archive's `COPYING` was found and hashed; its full GPL text was not
read in this pass.

The source bundle also contains zstd, lz4, xz and bzip2 downloads. They are
not evidence of corresponding standalone libraries in this rootfs.
The resolved configuration explicitly disables `CONFIG_PACKAGE_libzstd`
and `CONFIG_BTRFS_PROGS_ZSTD`. Host build tools and compression code within
the Linux kernel must be reviewed separately from these two userspace packages.

| Archive | File | SHA-256 |
| --- | --- | --- |
| zlib-1.3.1.tar.zst | LICENSE | 845efc77857d485d91fb3e0b884aaa929368c717ae8186b66fe1ed2495753243 |
| zlib-1.3.1.tar.zst | zlib.h | 8a5579af72ea4f427ff00a4150f0ccb3fc5c1e4379f726e101133b1ab9fc600c |
| lzo-2.10.tar.gz | COPYING | 8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643 |

The zlib.h hash identifies the complete header file, not just its license block.
