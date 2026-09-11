# Differences from official OpenWrt

Baseline: the commit in `openwrt.lock` (OpenWrt 25.12.5, Linux 6.12.94), with
all external feeds pinned in `feeds.lock`. The project builds from source;
it does not silently edit a downloaded DTB or patch a firmware binary.

## Source changes

| Input | Change | Reason |
| --- | --- | --- |
| `openwrt/patches/100-add-buffalo-ls420d-ram-initramfs-support.patch` | Native LS420D DTS derived from the official LS421DE hardware description | Disable absent NAND/PCIe/SD, describe USB power and board GPIOs, identify the actual board, preserve documented PHY settings |
| Same patch: image profile | RAM-only LS420D kernel image and packages | No LS421DE NAND/sysupgrade layout |
| Same patch: network and environment tools | Native identity handling and environment on mtd1 | Avoid reliance on a false LS421DE compatible identity |
| Same patch: linkstation-poweroff driver | Add LS420D match | Retain poweroff without the compatibility alias |
| Same patch: upgrade guard | Refuse flash/sysupgrade | This is a RAM boot project, not an installer |
| `kernel-patches/301-preserve-initrd2-with-mangle.patch` | Move ATAG_INITRD2 conversion outside the command-line-mangling exclusion; correct Kconfig help | Allow the external companion to reach Linux without accepting vendor memory tags or abandoning command-line filtering |

The external-initramfs change reuses the existing conversion code. It does not
disable mangling wholesale, alter U-Boot, implement a loader, or modify the
initramfs extraction algorithm. `tests/check-atags.py` runs the actual patched
converter natively with a small ARM header shim to check initrd forwarding and
preservation of memory/command-line policy.

## Configuration and common files are also deltas

`config/ls420d.config` is the explicit seed configuration. Its resolved hash
and the actual package manifest are recorded by the build. Storage diagnostics,
ethtool and cooling dependencies are part of the generic product, as are
`rsync` and `hd-idle` for the backup role. The router defaults of the mvebu
target (dnsmasq, odhcpd, ppp) are deselected: this is a single-port host, and
those services would only run idle. The host firewall stays.

`openwrt/files/` supplies DHCP-client networking, firewall and disabled/key-only
SSH defaults, plus PHY and fan services. These are additional runtime changes,
not part of the tiny ATAG fix. The fan policy starts CPU cooling at 60 °C,
uses other temperature sources too, and includes fault handling. Disk standby
and full native-board hardware behavior still require measurement.

`scripts/install-public-files.sh` installs only this public overlay.
`scripts/make_initrd.py` creates a separate data-only companion. Site and secret
inputs are never needed by the generic build.

## Inspect a particular build

Each successful full build produces the following. CI uploads only the
text-only evidence subset described in [distribution policy](distribution.md),
not the kernel/rootfs:

- `upstream-delta.patch`: staged source changes relative to the locked upstream
  commit, including the additional kernel patch. This intentionally excludes
  generated build files and the separately inventoried public overlay.
- `public-files.sha256`: hashes of the generic overlay sources.
- `kernel-patches.sha256`: hashes of the additional kernel-patch inputs.
- `rootfs-inventory.json`: actual built rootfs paths and entry types.
- `packages.manifest`: actual selected packages.
- `build.manifest` and `SHA256SUMS`: pinned inputs and output identities.

The source diff contains a kernel patch *as an OpenWrt source file*; inspect
`kernel-patches/` for the corresponding direct Linux diff. The resolved config
hash identifies configuration but is not itself the config text.

Do not equate this source-build profile with the old 25.12.2 bring-up image.
That pilot supplied evidence for the mechanism, not byte-for-byte equivalence
or validation of this newer kernel and native DTS.
