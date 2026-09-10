# Licensing and provenance

Repository-authored scripts and documentation are available under the MIT license
unless a file says otherwise. This repository-level choice does not relicense
OpenWrt, Linux, imported patches, device-tree sources, logs, or third-party work.

Before copying or adapting material:

1. record the source URL, exact commit, original path, author notices and license;
2. preserve compatible copyright notices and SPDX identifiers;
3. describe the adaptation in the patch commit message;
4. do not import material whose redistribution terms are unknown;
5. keep DTS contributions under their exact applicable upstream terms; the
   LS420D hardware reference is pinned to Debian_on_Buffalo commit
   `48084c9bb33a2ed9b6340969301c0265678d9d7d`, and its original `GPL-2.0+ OR MIT`
   meaning and author notice are preserved as `GPL-2.0-or-later OR MIT` in the
   OpenWrt patch;
6. review the complete tree again before making the repository public.

Links and independently written test hypotheses are not copied implementations.
Provenance records belong with the relevant finding or patch series, not solely
in transient pull-request discussion.

## Split-image contribution provenance

The CPIO codec, companion generator, fan/PHY services and host tests are
repository-authored MIT code, adapted from the project's local September 2026
RAM-only bring-up. Only the deployment-neutral implementations were imported;
no operational keys, device identities or private image archives were copied.

The ATAG patch modifies existing Linux conversion code after OpenWrt's
`target/linux/mvebu/patches-6.12/300-mvebu-Mangle-bootloader-s-kernel-arguments.patch`
from the exact commit in `openwrt.lock`. That Linux-derived change remains under
Linux's GPL-2.0 terms; the repository MIT license does not relicense it.
Its adaptation moves the existing INITRD2 handling outside the mangling guard
and updates the Kconfig explanation, without importing a different bootloader.
