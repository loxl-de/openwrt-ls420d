# OpenWrt for Buffalo LinkStation LS420D

Experimental RAM-only firmware integration, not an OpenWrt fork and not yet a
supported firmware release. The full source build is configured to run in GitHub Actions.

## Two boot files, one generic build

- **uImage.buffalo** contains the kernel, LS420D device tree, built-in OpenWrt
  root filesystem, common packages and hardware services. No deployment keys,
  host identity or backup destinations belong here.
- **initrd.buffalo** is a small external, uncompressed CPIO initramfs in a legacy
  U-Boot RAMdisk wrapper. Linux extracts it over the built-in RAM filesystem
  **before starting init**. It supplies site configuration and, for a private
  deployment, SSH credentials. There is no runtime deployment loader.

CI supplies an **anonymous example** companion: DHCP client, neutral hostname,
SSH disabled, no keys. It is a template, not a remotely accessible appliance.
Generate your private companion locally without rebuilding the kernel:
[deployment guide](docs/deployment.md).

## What differs from official OpenWrt?

The locked baseline is OpenWrt **25.12.5 / Linux 6.12.94**. Changes are separated:

1. Native LS420D device description, RAM-only image profile and board integration.
2. A small ARM ATAG conversion patch retaining external initramfs addresses while
   preserving OpenWrt's vendor command-line filtering.
3. Explicit package selection and generic, inspectable runtime files, including
   safe network defaults, PHY setup and temperature-based fan control.

See the [complete delta map](docs/upstream-delta.md). Every successful full build
publishes text-only evidence: source diff, package manifest, file inventory and
product checksums. Kernel/rootfs downloads remain gated by the
[corresponding-source policy](docs/distribution.md); the anonymous data-only
example remains downloadable.
This is **not** a claim that the result is an official image with only its DTB
changed.

## Status and boundaries

The split-image mechanism was hardware-tested with an earlier
**25.12.2 / Linux 6.12.74 pilot**. The native 25.12.5 build in this repository
requires its own cold/warm boot, network, external-initramfs and cooling tests.
Successful host tests or CI do not establish hardware support.

No flashing, disk partitioning, boot-environment modification, reboot or
deployment is performed by these build scripts. Existing stock boot priority
and a separately configured TFTP path are not changed by an image build.
Do not use LS421DE NAND installation or sysupgrade instructions on an LS420D.

## Start here

- [Build and CI lifecycle](docs/build.md)
- [Personalize the example initrd](docs/deployment.md)
- [Architecture and trust boundaries](docs/architecture.md)
- [Exact upstream deltas](docs/upstream-delta.md)
- [Hardware acceptance checklist](docs/hardware-test-protocol.md)
- [Roadmap](docs/ROADMAP.md)
- [Licenses and attribution](NOTICE.md)
- [Source publication checklist](docs/publication.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

Public standard runners are the intended canonical build infrastructure.
While the repository is private, automatic heavy firmware builds remain gated;
lightweight tests and example-initrd generation still run. A manual full build
can consume private Actions minutes. Changing visibility and releasing validated
firmware are separate decisions.

## Layout

```text
openwrt.lock, feeds.lock  immutable upstream inputs
config/                  explicit generic package/build selection
openwrt/patches/          native LS420D board and image integration
kernel-patches/           small external-initramfs kernel change
openwrt/files/            generic runtime files, never private provisioning
examples/                anonymous and private-configuration JSON templates
scripts/                 build, companion generator and audits
tests/                   host-side regression tests
docs/                    design, differences, instructions and evidence
private/                 ignored local provisioning inputs and output
```

Boot files containing private credentials must never be uploaded as public CI
artifacts. TFTP and legacy uImage CRCs provide **no authentication or secrecy**.
Use a trusted boot network and protect the TFTP server.
