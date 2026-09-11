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
