# Hardware checks on candidate 994e3c8

Overall result: **PARTIAL**. The tests below passed on pilot A, the same LS420D
used in the [12 September run](native-hardware-20260912.md). They do not certify
the previously damaged R106 area or complete the release gate. No UART contact,
flash write or partition-table change was used in this run.

## Build and deployment

Repository commit: `994e3c84bb921c2448c52086c6a8ed97d6f2f240`.
[GitHub candidate run 34784695003](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34784695003)
completed successfully. The downloaded manifest identifies that commit,
OpenWrt 25.12.5 and upstream commit `f0a60eee2fe051741c643ea6118718aae1ef17fb`.
The runtime reports Linux 6.12.94.

The generic image is 9,881,850 bytes, SHA-256:

```text
a955eab27c631498f8c6d6790651b298808228fbc82c4c68bcdff8de8d711a44
```

Downloaded assets matched `SHA256SUMS`. The manifest reports 8,325,766 bytes of
initrd headroom; this is the packaging bound, not measured free RAM.
The private format-2 companion is 4,160 bytes. It was generated from this
repository and supplies a static test network, existing SSH identities and the
optional backup configuration. Its keys, archive and deployment details remain
private. The public example was downloaded and hash-checked, but not booted.

The TFTP server recorded complete kernel and companion transfers at
22:58:17–22:58:43 UTC on 13 September. SSH confirmed the private marker, hostname
and the exact repository hash of `/usr/sbin/ls420d-pull`. Root and `/tmp` are
tmpfs, no swap is active, and the companion mounts disk A at `/mnt/backup`.
Both SPI-NOR partitions report flags `0x800`, with `MTD_WRITEABLE` clear.
This checks the kernel's advertised protection without attempting a write.
Password-only SSH was rejected with `Permission denied (publickey)`.

## Pull and restore

Both existing 1 TB test disks are separate Btrfs filesystems. No existing test
directories were deleted. The new destination and UUID marker were first created
on the preceding runtime; the final image then used those same destinations.

The actual companion-configured `/usr/sbin/ls420d-pull` pulled from an isolated
SSH source restricted to read-only rsync. A temporary loopback tunnel connected
the NAS to that source; host-key verification remained enabled. These tests do
not establish direct homelab routing or production source permissions.

The synthetic corpus contains boundary-sized files up to 8 MiB, Unicode and
space-containing names, an empty directory, a symlink, a hardlink pair, a named
user ACL and a user xattr. For each disk, the job returned `ok 0`, then
`rsync -aHAX --numeric-ids` restored its destination into RAM. Every expected
SHA-256 matched in the backup and restore. Checksum comparisons using
`rsync -naciHAX --numeric-ids` against the SSH source produced no changes.
Separate checks confirmed the hardlink inode pair and symlink target.

The final job also produced these results:

| Case | Observed result |
| --- | --- |
| Destination unmounted | Exit 1, `no-writable-btrfs-mount`; no RAM destination created |
| Lock held by another process | Exit 75 |
| Other disk mounted with mismatched configured UUID | Exit 1, `wrong-volume` |
| Source directory missing | Exit 23, recorded `failed 23` |
| Source restored | Exit 0, recorded `ok 0` |

The final-image missing-marker case and a detach during an active transfer were
not exercised. A missing mount before transfer is not that detach test.

## Cooling and boot recovery

A 15-minute CPU workload hashed `/dev/zero`, with an independent timed kill and
an 80 C abort threshold. All 45 samples reported fault 0; the maximum CPU reading
was 65.316 C. Fan state reached 2. Sleeping disks were skipped by temperature
reads while CPU and PHY monitoring continued. The fan-bound PHY zone remained
`enabled` under `user_space`.

After the load ended, the identified fan worker was stopped with SIGSTOP.
Within 12 seconds the supervisor selected full fan state 3 and replaced the
worker. Its new status reported fault 0 and alarm 0. Real sensor readings and
kernel thermal protection were never disabled. This tests a stalled worker,
not a disconnected sensor, a physically jammed fan or thermal emergency poweroff.

Three subsequent warm-boot exercises passed:

1. Change only the private companion's hostname, keeping the generic hash fixed.
2. Restore the retained previous image/companion pair and verify its older pull-job hash.
3. Restore the final generic image and normal companion, then run a successful pull.

Each SSH check used the pinned host identity and observed a new boot ID. A
temporary RAM marker disappeared after each reboot. Data mounts were unmounted
before reboot. One SSH restart took longer than the first check window but
returned without physical intervention. This is not a ten-boot reliability test.

## Standby test in progress

A controlled 24-hour idle interval started at `2026-09-13T23:23:06Z`, after the
last successful pull and return to the final image. Both disks are unmounted
and in standby. Cron is deliberately stopped for this interval; CPU, PHY and
fan monitoring remain active. This is not unattended daily scheduling coverage
or a mounted-volume standby test. The earliest endpoint is
`2026-09-14T23:23:06Z`; no passing duration is claimed yet.

At the 23:34 UTC sample both disks remained asleep, the boot ID was unchanged,
and block I/O counters matched the baseline. SMART start/stop and power-cycle
counters were recorded before standby for the final comparison.

Still open: the rest of the [hardware protocol](../hardware-test-protocol.md),
including repeated cold starts, sustained memory and concurrent storage load,
physical USB/LED/button coverage, absent/malformed companions, actual sensor/fan
faults, mounted-volume standby and the full idle duration. RTC and WoL were not
retested on this exact image. These omissions remain release-gate limitations.
