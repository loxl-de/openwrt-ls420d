# Boundary of the generic base system

The shared image should contain what every supported LS420D needs to boot,
remain reachable and cool itself. A site companion supplies deployment data.
Rsync belongs in this shared pull-backup base; destinations and jobs do not.

| Layer | Belongs here | Current implementation |
| --- | --- | --- |
| Board and boot | Native DTS, poweroff identity, external-initramfs handoff, RAM image profile | Small source patches, no U-Boot replacement |
| Common runtime | DHCP-client networking, key-only provisioning, fan control, PHY restart workaround | Public overlay; no disk overlay or automatic flash writer |
| Storage capability | Btrfs/ext4, mount discovery, SMART and standby tools | Present; disks are not mounted or put to sleep automatically |
| Site data | Hostname, addresses and SSH identities | Format-2 companion generated locally |
| Backup transport | rsync with ACL/xattr support and the existing Dropbear SSH client | Selected in the image; no rsync daemon |
| Backup jobs | Private daily job and volume identity | Optional single-job companion example; retention remains site policy |

## What to preserve

The two OpenWrt build fixes are not board features, but removing them reintroduces
observed parallel-build and timestamp failures. The memory-overlap check protects
the companion from a kernel that grows too large. Source collection, original
notices, hashes and an offline rebuild remain part of maintaining a distributable
image; they are not installed on the NAS.

Fan supervision is more code than a temperature curve because sensor reads can
stall and stopped workers must leave cooling enabled. Simplifying it requires
equivalent failure handling and hardware tests. The selected kernel provides the
user_space governor: bound thermal zones stay enabled and retain kernel critical
trips. The older disabled-zone fallback remains for kernels without that governor;
it is not the expected configuration of this image. Disk temperature reads are
skipped in standby, while CPU and PHY monitoring continue. These runtime changes
still require the new candidate's hardware acceptance tests.

The PHY service uses `ethtool wol g` as a warm-reboot workaround. Its presence
does not establish magic-packet wake from poweroff.

## Backup configuration

Rsync is now selected in the generic image, including ACL and extended-attribute
support. The existing Dropbear client supplies SSH without a second SSH package.
Packaging requires both the rsync package manifest entry and its executable in
the built rootfs. The kernel/companion memory checks still apply.

The retained hardware-tested candidate predates this addition and installed
rsync only temporarily. Do not mistake that older image for the new build.

Keep source hosts, client keys, known-host pins, filesystem UUIDs and schedules
private. A reusable backup example needs an identity-checked mounted destination,
a job lock, bounded logging, the real transfer exit status and no automatic
deletion by default. Installing a cron line alone does not satisfy those needs.
The optional [reference job](pull-backup-example.md) provisions only those inputs,
including the mount configuration and a daily cron entry. It does not import
arbitrary UCI files, archives or scripts. It is a current-copy example, not a
versioned or ransomware-resistant backup policy.

The NAS profile deselects dnsmasq, odhcpd, PPP and the U-Boot environment tools.
DHCP-client networking and the host firewall remain. Both SPI-NOR partitions must
be read-only in the compiled DTB, and packaging rejects router daemons or
environment tools that return through dependencies. The retained older hardware
candidate does not have these protections.

The existing hdparm tool is sufficient for manual standby tests; no additional
idle daemon starts automatically. iperf3, tcpdump and USB tools remain useful for
remote diagnosis on a device with inconvenient serial access.

Nano, tmux and UPS integration are optional application choices. They do not
belong in the minimal board-support patch. Adding rsync changes the package
selection, not the cooling policy, device tree or boot mechanism.
