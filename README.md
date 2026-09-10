# OpenWrt for the Buffalo LinkStation LS420D

This project develops an OpenWrt system that runs entirely in RAM on the Buffalo
LinkStation LS420D. The goal is a quiet pull-backup NAS that fetches backups from
other machines on its own schedule. Between backups, its hard drives can stay
in standby while the NAS remains reachable over the network.

The repository provides the operating-system build and configuration tools.
You configure backup jobs, storage layout and disk standby separately. Those
parts still need to be set up before using it as a backup server.

## Running without a mounted system disk

A disk-based operating system can keep a backup drive spinning even when no
backup is running. Running from RAM lets both drive bays hold data without a
permanently mounted system partition.

The NAS still needs somewhere to load its boot files from: a SATA boot partition
or a separately configured TFTP server on the network. Once Linux is running,
it no longer needs that storage. With network boot, you can prepare updates on
the server without removing a disk from the NAS.

Backup jobs and temperature monitoring must also avoid unwanted disk access;
running from RAM alone does not put the disks into standby.

## One shared operating system, your own configuration

The bootloader expects two files. This project uses them to keep the shared
operating system separate from the settings and credentials for your NAS:

- `uImage.buffalo` contains the shared operating system: the Linux
  kernel, the LS420D hardware description, OpenWrt, selected tools and common
  services such as fan control. The same image can serve multiple devices.
- `initrd.buffalo` contains your configuration: the hostname, network
  settings and SSH access credentials. A local generator creates this small
  file from your settings and keys. They do not go into the public build.

Linux unpacks the operating system into RAM, adds the configuration from the
second file, and only then starts services. This uses Linux's existing
initramfs mechanism: an archive of files loaded during boot.

A kernel or package update needs a new shared image. Changing a hostname or SSH
key needs only a new configuration file, without compiling Linux again. Keep a
known-good pair so you can return to it if an update fails.

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
