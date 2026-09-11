# OpenWrt for the Buffalo LinkStation LS420D

This repository provides build recipes, documented patches and configuration
tools for running OpenWrt on the Buffalo LinkStation LS420D. Its purpose is to
make the firmware reproducible and updatable as OpenWrt evolves, while allowing
owners to adapt it to their own devices and uses.

The design separates the firmware into two boot artifacts: a shared kernel and
base system, kept as close to official OpenWrt as possible, and a custom initrd
companion for deployment-specific configuration.

## Design: minimal kernel changes, flexible initrd companion

1. **Keep the custom kernel close to upstream.** Change only what is needed for
   the LS420D and this boot method. Keep those changes small and documented so
   they can be reviewed and carried forward when OpenWrt is updated.
   Device-specific settings and credentials belong outside the shared image.
2. **Put customization in a separate initrd.** The shared image should be usable
   across different deployments. A locally generated companion supplies the
   files that configure it for a particular NAS, without rebuilding the kernel
   or putting private settings into the public build.

The two artifacts use the filenames expected by Buffalo's bootloader:

- `uImage.buffalo` contains the Linux kernel, the LS420D hardware description
  and the shared OpenWrt base system. It includes selected tools and common
  services such as fan control. It is more than a kernel binary; the same
  image can serve multiple devices.
- `initrd.buffalo` is the custom companion. Linux unpacks its files over the
  base system in RAM before starting services. This is the place for
  deployment-specific configuration, including credentials.

The companion uses Linux's existing initramfs mechanism, an archive of files
loaded during boot. Configuration takes effect before services start, without
a separate post-boot loader. The archive can add or replace files in the base
system; its design is not limited to a fixed set of network or SSH settings.

The generator accepts two kinds of input. A small JSON description covers
hostname, network settings and SSH access credentials for a first boot. A
configuration backup taken on the running NAS with `sysupgrade -b` covers
everything you configured interactively afterwards: UCI files, SSH keys, the
crontab, hosts and accounts. Both routes produce an archive without
additional program files: scripts and executables are rejected, and settings
that would otherwise be lost at reboot become the next companion instead.
The companion is trusted private configuration, not a sandbox for foreign
input; a crontab names commands that the image already contains.

A kernel or package update needs a new shared image. A configuration change
needs only a new companion, provided it remains compatible with the base system.
Changing a hostname or SSH key therefore needs no Linux compilation. Keep a
known-good pair so you can return to it if an update fails.

## Use case: an off-disk backup system

The intended use is a quiet pull-backup NAS that fetches backups from other
machines on its own schedule. Between backups, its hard drives can stay in
standby while the NAS remains reachable over the network.

The operating system runs entirely in RAM, so both drive bays can hold data
without a permanently mounted system partition keeping a disk spinning.
Boot files can come from a SATA boot partition or a separately configured TFTP
server. Once Linux is running, it no longer needs that boot storage. Network
boot also removes the need for a local boot partition and lets you prepare
updates on the server without removing a disk from the NAS.

You configure backup jobs, storage layout and disk standby separately.
Backup jobs and temperature monitoring must avoid unwanted disk access;
running from RAM alone does not put the disks into standby. This repository
provides the operating-system build and configuration tools, not a finished
backup appliance.

Interactive changes disappear at reboot. To make them permanent, put them in
the build inputs or your local configuration and regenerate the relevant file.

## OpenWrt with a small set of changes

OpenWrt provides a compact Linux system, a package collection and an established
build process. This project uses it to run a NAS rather than a router. The
selected tools include Btrfs support, SMART diagnostics, disk and network tools;
shared hardware services handle the fan and Ethernet setup.

The changes to upstream OpenWrt are:

- An LS420D-specific hardware description and RAM-boot image profile, based on
  OpenWrt's support for the related LS421DE but accounting for hardware differences.
- A small kernel change that lets the external configuration archive reach
  Linux. OpenWrt's boot-argument filtering otherwise removes the information
  needed to load it.
- Build recipes, a configuration generator and tests to maintain this setup
  across OpenWrt updates.

The [upstream change guide](docs/upstream-delta.md) explains each modification.
Full builds are intended to run on standard GitHub Actions runners, which are
free for public repositories. OpenWrt and its package sources are pinned to
exact revisions. Others can rebuild from the same inputs without maintaining
a local compiler setup.

## Current status

An earlier OpenWrt 25.12.2 / Linux 6.12.74 pilot booted on a real LS420D,
ran from RAM and provided SSH access. Configuration from the second boot file
appeared in the running system. See the
[hardware bring-up record](docs/findings/local-bringup.md).

The current repository targets OpenWrt 25.12.5 / Linux 6.12.94. Tests that run
without the NAS, checks of the upstream sources and generation of the example
have passed in GitHub Actions. This newer version still needs a complete build
and testing on the NAS before it can be released as supported firmware.

You can download the example `initrd.buffalo`, which contains neutral settings,
no keys and disabled SSH. There is currently no downloadable generic kernel.
The GitHub Actions workflow can compile it, but downloads remain on hold until
the accompanying source and license package is ready. The [build guide](docs/build.md)
and [distribution policy](docs/distribution.md) describe that process.

## Where to go next

The [configuration guide](docs/deployment.md) shows how the example becomes
your own `initrd.buffalo`. The [architecture document](docs/architecture.md)
explains the boot sequence and treatment of credentials. For development,
see the [hardware test checklist](docs/hardware-test-protocol.md) and
[contribution guide](CONTRIBUTING.md).

Establish a recovery route before booting a candidate. These tools do not
configure the bootloader, flash the NAS or partition disks. LS421DE NAND
installation instructions do not apply to the LS420D.

Keep your configuration file private and use a trusted boot network: it
contains credentials, and TFTP does not encrypt or authenticate the transfer.
See [security](SECURITY.md) and [licenses and attribution](NOTICE.md).
