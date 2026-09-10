# Source publication and binary distribution

## Current enforced policy

Public source development and full compilation on standard GitHub runners are
enabled independently of firmware distribution. The workflow builds the complete
firmware, runs its packaging checks and uploads **text-only compile evidence**.
An explicit allowlist excludes all kernel/rootfs binaries. Reproducibility jobs
compare SHA-256 digests of the actual products built on independent runners.
This is a hash comparison, not a downloaded byte-for-byte comparison.

The separate anonymous data-only example companion is still downloadable. It
contains no kernel, executable OS, keys or operating configuration for a real
site. Its MIT license accompanies it. Nothing runs on the NAS from CI.

Firmware upload cannot be enabled with a dispatch input or repository variable.
It requires a reviewed workflow change implementing the source requirements
below. This is a temporary **distribution** gate, not a claim that a kernel
must be hardware-validated before its source can be public.

## Acceptance criteria for downloadable firmware

Before enabling any public kernel/rootfs download, including an experimental
Actions artifact, maintainers must validate the exact package set and provide:

1. The exact project revision, OpenWrt and feed sources, local changes, build
   and installation scripts. A commit hash is an identifier, not source content.
2. The source archives actually consumed by the build, including any generated
   or otherwise unavailable inputs, and the package-specific patches/recipes.
   A warm download cache must not conceal a missing source input.
3. The resolved OpenWrt and Linux configurations, package/version inventory,
   toolchain identity, build instructions and a source-to-binary manifest.
4. Relevant copyright notices, license texts and redistribution conditions
   for Linux and every selected package. Preserve third-party attribution.
5. Sources obtainable alongside the corresponding binaries for the period
   required by their licenses; do not rely on a short-lived CI artifact or
   someone else's mutable download URL as the sole source offering.
6. An independent offline-source rebuild check, using the supplied sources,
   with failures treated as missing-source findings. Build reproducibility is
   checked separately; a matching hash alone does not validate license compliance.

This process should run on public standard GitHub runners. A sources bundle
may be larger than the firmware; budget storage and retention explicitly.
Keep source archives and firmware paired when publishing and retiring versions.
Do not use a bare promise of future source availability as a substitute.

Existing private experimental firmware is not part of the public source release.
Preserve it outside the public repository before retiring old GitHub artifacts,
or use a fresh source-only repository that does not inherit those artifacts.

## Scope of review

The project has not yet validated a complete corresponding-source bundle for
the new native build. Accordingly the CI gate remains closed. Local builds
remain possible, but anyone redistributing them must satisfy the same conditions.

Primary references: [OpenWrt licensing](https://openwrt.org/license),
[GPLv2 text](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html),
[GNU source distribution FAQ](https://www.gnu.org/licenses/gpl-faq.html#UnchangedJustBinary).
