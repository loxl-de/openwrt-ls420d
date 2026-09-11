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
