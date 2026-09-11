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

The marker `/etc/ls420d-deployment` identifies companion format 2; it is not a
signature or a binding to a particular kernel hash. Format 2 delivers the
hostname as UCI batch data in `/etc/ls420d-site.uci`, which a uci-defaults
hook in the generic image merges after `config_generate` has produced the
board defaults. Shipping a whole `/etc/config/system` instead would stop that
generation and silently drop the LED, button and logging entries. A format 2
companion therefore needs a generic image that carries the hook; on an older
image only the hostname stays at its default. Verify downloaded hashes and
hardware-test the intended pair. Preserve a known-good pair privately.

See [deployment](deployment.md), [build](build.md) and
[ADR 0002](decisions/0002-generic-kernel-external-initramfs.md).
