# OpenWrt for the Buffalo LinkStation LS420D

This project develops a RAM-based Linux system for the Buffalo LinkStation
LS420D. The goal is a quiet **pull-backup NAS**: it fetches backups from other
machines on its own schedule, then puts its hard drives into standby while
remaining reachable over the network.

The repository provides the operating-system build and configuration tools.
Backup jobs, storage layout and disk-sleep policy are configured separately;
this is the foundation for a backup server, not a finished backup appliance.

## Why run a NAS from RAM?

A backup disk should not have to keep spinning because it also holds the
operating system. Running from RAM lets both drive bays serve as data storage,
without a permanently mounted system partition.

Booting and running are separate concerns. The boot files can come from a SATA
boot partition or a separately configured TFTP server on the network. After
boot, Linux no longer depends on that storage. With network boot, updates can
be prepared on the server without removing a disk from the NAS.

RAM-only operation makes disk standby possible, not automatic: backup jobs and
temperature monitoring must also avoid unwanted disk access.

## One shared operating system, your own configuration

Software common to every LS420D and settings belonging to one particular NAS
are delivered separately, using two filenames expected by Buffalo's bootloader:

- **`uImage.buffalo` — the shared operating system.** It contains the Linux
  kernel, the LS420D hardware description, OpenWrt, selected tools and common
  services such as fan control. The same image can serve multiple devices.
- **`initrd.buffalo` — your configuration.** It supplies the hostname, network
  settings and SSH access credentials. A local generator creates this small
  file from your settings and keys; they do not go into the public build.

Linux unpacks the operating system into RAM, adds the configuration from the
second file, and only then starts services. This uses Linux's existing
initramfs mechanism: an archive of files loaded during boot.

The benefit is independent updates. A kernel or package update needs a new
shared image. Changing a hostname or SSH key needs only a new configuration
file, without compiling Linux again. Keep a known-good pair for rollback.

Interactive changes disappear at reboot. To make them permanent, put them in
the build inputs or your local configuration and regenerate the relevant file.

## Why OpenWrt, and what does this repository add?

OpenWrt provides a compact Linux system, a package collection and an established
build process. Here it is used as a NAS operating system, not as a router. The
selected tools include Btrfs support, SMART diagnostics, disk and network tools;
shared hardware services handle the fan and Ethernet setup.

This repository maintains a small set of changes on top of upstream OpenWrt:

- An LS420D-specific hardware description and RAM-boot image profile, building
  on OpenWrt's support for the related LS421DE without assuming identical hardware.
- A small kernel change that lets the external configuration archive reach
  Linux. OpenWrt's boot-argument filtering otherwise suppresses the information
  needed to load it.
- Build recipes, a configuration generator and tests to maintain this setup
  across OpenWrt updates.

The [upstream change guide](docs/upstream-delta.md) explains each modification.
Full builds are intended to run on standard GitHub Actions runners, using the
free infrastructure available to public repositories. OpenWrt and its package
sources are pinned to exact revisions, so others can rebuild from the same
inputs without maintaining their own compiler setup.

## What works today?

An earlier **OpenWrt 25.12.2 / Linux 6.12.74** pilot booted on a real LS420D,
ran from RAM and provided SSH access. It also demonstrated that configuration
from the second boot file appeared in the running system. See the
[hardware bring-up record](docs/findings/local-bringup.md).

The current repository targets **OpenWrt 25.12.5 / Linux 6.12.94**. Its host-side
tests, upstream-source checks and example generation have passed in GitHub
Actions. A complete build and hardware acceptance of this newer version are
still outstanding; it is not yet a supported firmware release.

You can download the example `initrd.buffalo`, which contains neutral settings,
no keys and disabled SSH. There is currently **no downloadable generic kernel**:
CI is configured to compile it, but kernel downloads remain on hold until the
accompanying source and license package is ready. The [build guide](docs/build.md)
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
