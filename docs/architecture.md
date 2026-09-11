# RAM-only split-image architecture

## Boot contract

Stock U-Boot loads a legacy kernel uImage and a legacy RAMdisk image. For this
project their Buffalo filenames are `uImage.buffalo` and `initrd.buffalo`.
The kernel image includes its generic rootfs and appended LS420D DTB.

Linux first expands the built-in initramfs and then the external CPIO archive.
Only after both does it start init. The second archive can therefore replace
configuration files before services start. **No post-boot loader is involved.**

OpenWrt's ARM command-line mangling previously filtered ATAG_INITRD2 together
with other vendor tags. The small kernel patch passes only the external
initramfs start/end through to the device tree; memory tags remain filtered.
It does not remove OpenWrt's command-line policy.

The generic image must remain usable as a diagnostic RAM system without
private provisioning, but not expose passwordless SSH. Its Dropbear instance
is disabled. The example companion also leaves it disabled; a generated
private companion enables key-only SSH. This describes normal boot, not an
assertion that upstream physical-console/failsafe recovery has been removed.
Physical access and the boot network remain trusted.

## Three custody levels, not three secure-boot stages

1. Public, reviewable common code: kernel, rootfs, services and package selection.
2. Site configuration: hostname and network settings, maintained locally.
3. Secrets: especially the NAS SSH host private key, kept locally.

Levels 2 and 3 are delivered together as a private companion for this minimal
implementation. The generator accepts a constrained configuration schema and
writes data files only. The kernel itself does not enforce that restriction:
an attacker able to replace the CPIO can replace executable files too.

Legacy image CRCs detect accidental corruption, not malicious modification.
TFTP is plaintext. A compromised boot server or untrusted boot network can
compromise the device and its credentials. This is not verified or secure boot.

## RAM and storage

The root filesystem and deployment files live in RAM. This implementation
does not mount a writable disk overlay, run extroot or write settings back on
shutdown. Changes made interactively disappear at reboot unless incorporated
into the appropriate source or private configuration and regenerated.

Backup disks are independent data devices. Their lifecycle, sleep policy and
backup schedules are not provisioned by the example. RAM root alone does not
prove disk standby: drivetemp polling and any backup or monitoring program
must be tested for interference with the intended sleep policy.

### Where state lives

RAM-only is a decision with consequences that need a home for each kind of
state, otherwise a power loss resets a backup system to zero:

- **Configuration** lives in the companion. Change it on the running system,
  capture it, regenerate; see [deployment](deployment.md).
- **Logs** are lost with the RAM root. Send them off the device: `logd`
  forwards to a remote syslog host with `uci set system.@system[0].log_ip`
  and `log_port`. The backup source host is a natural receiver, because it is
  awake whenever the NAS does anything interesting. Do not log to the data
  volume; that keeps a disk awake.
- **Job state** such as rsync snapshots, restic or borg repositories and
  their caches belongs on the data volume next to the data it describes.
  It is the backup, not the operating system, and travels with the disks.
- **SMART history** is not kept. Query it on demand or let the source host
  collect it over SSH; a monitoring cron job on the NAS would wake the disks.

### Boot source

Buffalo's U-Boot loads both files from the same source, so the host key in
the companion is exposed wherever `initrd.buffalo` lives. Two sources are
valid and they trade different things:

- **TFTP network boot** keeps the disks entirely free of operating-system
  files, so a data disk can be moved or replaced without touching a boot
  partition, and updates are staged on the server without opening the NAS.
  This is the disk-free operation the project has reached. Its cost is the
  plaintext companion on the boot network: keep the TFTP server on a boot
  VLAN or a directly attached link, restrict it to the NAS's address, and
  serve nothing else from it.
- **A SATA boot partition** keeps the key inside the enclosure. The files
  are read once at boot from a disk that then goes back to sleep; the boot
  partition is not mounted after Linux starts and does not keep the disk
  awake. Its cost is a small system partition on a data disk.

Choose by which exposure matters more on your network. Neither source
authenticates the images; see the boot contract above.

### Memory size comes from the device tree

The kernel patch keeps OpenWrt's policy of discarding the bootloader's
memory tags, so the RAM size is whatever the LS420D device tree declares:
512 MB, inherited from the LS421DE description and confirmed by the
community LS420D device tree. A board variant with less memory would not
boot this image. The hardware protocol checks the reported size against the
physical inventory for that reason.

## Common hardware services

The public overlay includes a PHY service that reapplies Wake-on-LAN setup,
and a fan service using CPU, PHY and HDD temperatures. CPU cooling starts at
60 °C; missing/stale sensor data triggers conservative cooling. The service
also implements shutdown thresholds and a supervisor. These are shared board
support, not site secrets.

The controller takes ownership of fan-associated thermal zones; it must be
validated together with the native DTS. The earlier pilot's success does not
prove identical behavior with this kernel/DTB. Wake-on-LAN enablement likewise
does not guarantee successful warm boot or RTC wake on every bootloader state.

## Versioning and updates

The generic image is built from locked OpenWrt and feed commits with its own
matching modules. Do not mix modules from another kernel build. Package or
kernel changes require a new generic build. Site-only changes require only a
new companion, provided the deployment contract is still compatible.

The marker `/etc/ls420d-deployment` identifies companion format 1; it is not a
signature or a binding to a particular kernel hash. Verify downloaded hashes
and hardware-test the intended pair. Preserve a known-good pair privately.

## Alternatives considered

**Debian** through Debian_on_Buffalo targets this exact board and has native
packages for every backup tool. It was retired for this project in favour of
the smaller RAM root and the reproducible cross-build; see
[the contribution guide](../CONTRIBUTING.md). The device-tree and boot work
would be the same there.

**Alpine Linux** in diskless mode, with the `apkovl` overlay and `lbu`, is
the closest existing implementation of this architecture: a generic image
plus a small archive of local changes applied at boot. It was not chosen
because it would not remove the board-specific work (the LS420D device tree,
the external-initramfs handoff under Buffalo's U-Boot, the fan and power-off
support) while dropping the OpenWrt integration that already carries it.

**OpenWrt** was chosen for the small RAM root, the existing LS421DE board
support, the reproducible pinned source build and procd/UCI as a
configuration layer. Its cost is that the backup application layer is not a
first-class citizen and has to be assembled from packages, which
[the reference job](pull-backup-example.md) does.

See [deployment](deployment.md), [build](build.md) and
[ADR 0002](decisions/0002-generic-kernel-external-initramfs.md).
