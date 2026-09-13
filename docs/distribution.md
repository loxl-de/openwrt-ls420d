# Sources, candidate retention and public release

Ordinary CI builds firmware and uploads allowlisted text evidence and an
anonymous example companion. It does not publish the generic kernel.
The manually dispatched [candidate workflow](candidate-build.md) retains
firmware, matching sources and notices in an unpublished release draft.
Neither workflow deploys a NAS.

A draft is preparation for review, not a release or support claim. There is
no dispatch switch that authorizes public firmware distribution.

## What must accompany firmware

Before a public download is enabled, review the exact package set and retain:

1. The committed project, OpenWrt and feeds, including patches, recipes and
   build/installation scripts. Revision identifiers alone are not sources.
2. The downloaded source inputs actually needed to rebuild, resolved OpenWrt
   and Linux configurations, package inventory, compiler identity and manifests.
3. Applicable original copyright notices, license texts and redistribution
   conditions, including mixed-license components within one package.
4. Durable source access alongside the matching binaries. Temporary CI
   artifacts or somebody else's mutable download links are not the release
   source offering.
5. An independent rebuild from that source bundle without network or compiler
   cache, distinguishing compilation, configuration and product-hash results.
6. The required hardware/recovery and security review. The full hardware gate
   in [the protocol](hardware-test-protocol.md) remains unchanged.

Do not remove source or notice obligations to simplify this repository.
Primary references: [OpenWrt licensing](https://openwrt.org/license),
[GPLv2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html) and the
[GNU source-distribution FAQ](https://www.gnu.org/licenses/gpl-faq.html#UnchangedJustBinary).

## Collection and pairing

`collect-source-review.py` archives committed sources, downloads, resolved
configs and build metadata. It excludes Git credentials, private worktree files
and built firmware. Its checksums bind each input; original notice files are
selected by name and by the pinned exceptions in `config/notice-files.json`.

`stage-candidate.py` verifies source and product inventories and rejects a
mismatched build before pairing them. The release packager uses this validation
and produces the seven assets described in [candidate-build.md](candidate-build.md).
Ordinary CI does not also copy a second full candidate tree only to discard it.

Generated review flags start as false. They are not toggled merely because a
build succeeds: the separate review record must identify the exact assets and
the evidence supporting approval.

## Offline rebuild

Run **Offline source rebuild** with the source-review artifact ID and the
independently checked SHA-256 of its ZIP. The existing CI dispatch inputs can
also call this workflow on a review branch while skipping ordinary compilation.

The workflow verifies every archive member, restores confined source trees
into fresh directories, then enters an empty network namespace as an ordinary
user. Loopback remains enabled for fakeroot's local TCP communication.
The runner PATH is retained so configuration probes see the same host tools.

No toolchain, object files or compiler cache are restored. The test checks the
OpenWrt configuration, compares the Linux configuration with only validated
initramfs source-root rebasing, runs the ATAG and packaging checks, and compares
kernel, companion and package-manifest hashes. A mismatch remains a failure.
There is no automatic second serial build after a failed compile.

Three reports are retained: product verdict, kernel-configuration comparison
and a rootfs inventory of paths, types, permissions and content hashes.
The former per-APK and per-ELF diagnostic parsers are no longer prerequisites
for a normal build. Their historical results remain accessible through
[the evidence index](findings/README.md).

The retained candidate passed the independent
[offline rebuild](findings/offline-source-path.md), and main's
[A/B comparison](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34739045121)
passed too. The verified offline method uses the original absolute build path;
it does not prove arbitrary-path or arbitrary-runner reproducibility.
The [release review](findings/release-review-20260913.md) records asset inspection.
None of these results converts partial hardware qualification into full support.
