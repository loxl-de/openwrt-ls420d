# Buildbot configuration experiment, 2026-09-11

Question: can OpenWrt's BUILDBOT mode omit the transient public APK signing key
without adding unrelated software or disabling package signature checks?

This was a configuration-only test using the verified source bundle from
[run 34539424333](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34539424333).
The canonical LS420D patch was applied, archived feed recipes were indexed and
installed, and `make defconfig` reproduced the archived configuration exactly.
No firmware was compiled locally. The repository configuration is unchanged.

Baseline resolved config SHA-256:
`33e77ec2d3eb5470c595389cee3974e18d96ab376ab4d455f5ea4396e4e51eda`.

## Configuration result

Enabling BUILDBOT also enables defaults for SDKs, additional packages and build
products. The experiment explicitly disabled ALL, ALL_NONSHARED, ALL_KMODS,
SDK, SDK_LLVM_BPF, IB, MAKE_TOOLCHAIN, COLLECT_KERNEL_DEBUG and
JSON_CYCLONEDX_SBOM.

That still selected `owut` and dependencies including RPC services.
The default is in `feeds/packages/utils/owut/Makefile`.
After explicitly disabling PACKAGE_owut, the resolved configuration differed
from the baseline in exactly four values:

```
CONFIG_BUILDBOT=y
CONFIG_REPRODUCIBLE_DEBUG_INFO=y
CONFIG_KERNEL_BUILD_USER="builder"
CONFIG_KERNEL_BUILD_DOMAIN="buildhost"
```

All package selections remained identical. SIGNED_PACKAGES and SIGNATURE_CHECK
remained enabled. Candidate resolved config SHA-256:
`7ba76e7727cdf6ca31d7fc6c4e96632f545faf1fd49aea04959e24be0badc74d`.

## Behavior outside the resolved configuration

`include/feeds.mk` also adds a kernel-module repository URL under BUILDBOT.
That URL includes Linux version, release and OpenWrt's configuration-derived
vermagic. `include/kernel.mk` puts the same identity into kernel-module package
dependencies. This does not establish compatibility with official modules:
the project has its own kernel configuration and patches. Matching modules
must come from the same generic build, as stated in the
[update contract](../architecture.md#versioning-and-updates).
Do not force package dependencies or substitute another kernel's modules.

`toolchain/Makefile` enables a Git-revision stamp check under BUILDBOT.
When the stamp differs, it removes generated build and staging directories.
The experiment did not execute this compilation path.

The source-backed random-key hypothesis still needs the file-level evidence
from the [diagnostic comparison](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34577568680).
The result above narrows a possible fix; it is not evidence that BUILDBOT alone
makes the firmware reproducible. No package trust checks were relaxed.
