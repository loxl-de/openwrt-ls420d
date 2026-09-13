# Boundary of the generic base system

The shared image should contain what every supported LS420D needs to boot,
remain reachable and cool itself. A site companion supplies deployment data.
Keep application choices separate from board support.

| Layer | Belongs here | Current implementation |
| --- | --- | --- |
| Board and boot | Native DTS, poweroff identity, external-initramfs handoff, RAM image profile | Small source patches, no U-Boot replacement |
| Common runtime | DHCP-client networking, key-only provisioning, fan control, PHY restart workaround | Public overlay; no disk overlay or automatic flash writer |
| Storage capability | Btrfs/ext4, mount discovery, SMART and standby tools | Present; disks are not mounted or put to sleep automatically |
| Site data | Hostname, addresses and SSH identities | Format-2 companion generated locally |
| Backup application | Pull transport, schedule, volume identity, retention and restore rules | Not provisioned yet |

## What to preserve

The two OpenWrt build fixes are not board features, but removing them reintroduces
observed parallel-build and timestamp failures. The memory-overlap check protects
the companion from a kernel that grows too large. Source collection, original
notices, hashes and an offline rebuild remain part of maintaining a distributable
image; they are not installed on the NAS.

Fan supervision is more code than a temperature curve because sensor reads can
stall and stopped workers must leave cooling enabled. Simplifying it requires
equivalent failure handling and hardware tests. Its present thermal-zone takeover
disables the kernel governor and relies on userspace critical limits. Retaining
kernel critical-trip handling is a separate safety improvement to evaluate,
not something this repository cleanup silently changes.

The PHY service uses `ethtool wol g` as a warm-reboot workaround. Its presence
does not establish magic-packet wake from poweroff.

## Next runtime change

Add the actual pull-backup transport to the shared image before calling it a
backup-ready base. The present hardware test installed rsync into RAM temporarily;
it is absent after reboot. The package choice and outgoing SSH support should
be built together and checked against the companion memory budget.

Keep source hosts, client keys, known-host pins, filesystem UUIDs and schedules
private. A reusable backup example needs an identity-checked mounted destination,
a job lock, bounded logging, the real transfer exit status and no automatic
deletion by default. Installing a cron line alone does not satisfy those needs.
Extend the companion schema only for the configuration that this example uses;
do not add a second general-purpose UCI or backup-archive parser pre-emptively.

Consider removing inherited router and flash-management packages only in that
separate runtime change. The current tested image still contains such packages;
a sysupgrade guard is not a kernel-enforced read-only SPI-NOR policy. Likewise,
iperf3, tcpdump and USB tools are useful diagnostics, not mandatory backup
dependencies. Measure their cost in the resolved image before trading away
remote diagnosis on a device with inconvenient serial access.

Nano, tmux and UPS integration are optional application choices. They do not
belong in the minimal board-support patch. No runtime package selection, cooling
policy or boot behavior changes as part of the repository cleanup.
