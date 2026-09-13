# OpenWrt for the Buffalo LinkStation LS420D

A disk-independent OpenWrt base system for a quiet pull-backup NAS. Linux and
the operating system run entirely in RAM, leaving both SATA bays available for
data. The disks can be unmounted and stopped between backups without taking
the operating system offline.

The repository maintains a small integration layer over official OpenWrt:
the LS420D hardware description, the changes needed for RAM boot, shared
hardware services, and tools to build and configure the result.

## Two boot files, two update paths

- **`uImage.buffalo`** contains the Linux kernel, LS420D device tree and generic
  OpenWrt root filesystem. Keep this image close to upstream and identical
  across deployments. Build it on GitHub Actions from pinned sources.
- **`initrd.buffalo`** is a small, locally generated configuration companion.
  Linux unpacks it over the generic filesystem in RAM before starting services.
  A configuration or key change needs a new companion, not a kernel build.

The kernel patch forwards the external initramfs address and size while
preserving OpenWrt's boot-argument filtering. There is no post-boot downloader,
persistent disk overlay or replacement bootloader. The
[upstream delta](docs/upstream-delta.md) lists the actual changes, including the
two build-system fixes.

The current companion generator supplies hostname, DHCP/static IPv4 settings,
SSH authorization and a persistent SSH host identity. Linux's archive mechanism
can replace other files too, but the generator intentionally accepts only its
documented schema. Configuration and credentials stay outside the public build.

## What the base system provides

Btrfs/ext4 support, storage and network diagnostics, CPU/HDD-aware fan control,
and the Ethernet PHY workaround used by the tested warm-boot path. Normal-boot
SSH is disabled until a private, key-only companion enables it.

Boot files may come from an existing SATA boot partition or an established
TFTP setup. Once Linux starts, neither is needed for the running root filesystem.
TFTP allows boot-file updates without moving disks, but requires a boot server
and a trusted network: the private companion is not encrypted in transit.

This is a base system, not a configured backup appliance. The current image
does not include rsync or provision backup accounts, schedules, disk identities,
retention, UPS shutdown or RTC alarms. Interactive package installations and
configuration changes disappear at reboot. See
[the base-system boundary](docs/base-system.md) before extending it.

## Current evidence

The retained OpenWrt 25.12.5 / Linux 6.12.94 candidate has completed native boot,
warm reboot, a configuration-only update, rollback, one RTC-wake cycle and
small storage tests on one LS420D. The
[hardware record](docs/findings/native-hardware-20260912.md) names the exact
image and limits. Full hardware qualification remains incomplete; Wake-on-LAN
from poweroff is not established.

The candidate also passed a cache-free, network-isolated
[rebuild from archived sources at the original build path](docs/findings/offline-source-path.md).
Independent main-branch builds matched in
[run 34739045121](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34739045121).
This does not establish reproducibility at arbitrary build paths or on every
runner image.

The anonymous example companion is downloadable and leaves SSH disabled.
Generic firmware and matching sources are retained in an unpublished candidate
draft, accessible to repository users with push access. Public firmware
distribution remains subject to [release review](docs/distribution.md).
Do not rebuild an existing candidate merely to retrieve it.

## Use and development

- [Create your own companion](docs/deployment.md).
- [Build and test](docs/build.md), or [retrieve a retained candidate](docs/candidate-build.md).
- [Understand boot and credential handling](docs/architecture.md).
- [Review the remaining work](docs/ROADMAP.md) and [hardware protocol](docs/hardware-test-protocol.md).
- [Contribute](CONTRIBUTING.md); see [security](SECURITY.md) and [attribution](NOTICE.md).

Establish a recovery route before booting a candidate. These tools do not
partition disks, flash the NAS or configure its bootloader. LS421DE NAND
installation instructions do not apply to the LS420D.
