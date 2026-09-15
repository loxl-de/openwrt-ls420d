# Hardware follow-up on candidate 37b9573

Overall result: **PARTIAL**. This run follows the
[994e3c8 tests](native-hardware-20260913.md) on the same pilot. Earlier results
remain attached to that earlier image; they are not a full acceptance of this one.

## Unrelated disk wakeup and fix

After the earlier standby test, `block info /dev/sda1` woke disk B and added
47 reads, or 1,560 sectors. Mounting A alone left B asleep. The pull job used
that probe and reproduced the wakeup. This occurred during further testing,
not during the completed 25-hour idle interval.

[PR #27](https://github.com/loxl-de/openwrt-ls420d/pull/27) replaced the probe
with `btrfs filesystem show --mounted .`. Live tests of a separate RAM copy
confirmed a successful pull, rejection of a wrong UUID, and unchanged counters
on the sleeping non-target disk. The reciprocal test passed on disk B.

## Built image and deployment

Repository commit: `37b95730f4e375e9ae46b7cb97747c94d6c46054`.
[Candidate run 34924688877](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34924688877)
succeeded. The downloaded kernel, example companion and manifests matched
their checksums. The source and notices archives were not downloaded in this run.

The generic image is 9,883,202 bytes, SHA-256:

```text
1867b11c7d69adec1806739473209cf48090e14723589ff8f5619c6b54023965
```

The retained private 4,160-byte companion was reused. TFTP completed both
transfers at 04:59:43 UTC on 15 September. SSH observed a new boot ID, discarded
volatile state and verified the installed pull job against the repository hash.
The previous boot pair was preserved. No flash or partition-table writes occurred.

Root and `/tmp` remain tmpfs, with no swap. Both MTD partitions report `0x800`
flags. Cron was stopped for controlled tests; unattended scheduling is not proven.

## Tests on the installed image

Both disks passed actual pull and fresh RAM restore checks for SHA-256,
ownership, ACLs, xattrs, hardlinks and symlinks. The non-target disk stayed
in standby with unchanged I/O counters during each pull. Both disks were
unmounted and returned to standby afterwards.

Missing mount, held lock, wrong UUID and missing source returned 1, 75, 1 and
23 respectively. No destination appeared in RAM when the mount was absent.
Restoring the source produced exit 0.

A separate temporary crond instance invoked the installed job at a minute
boundary. It returned `ok 0`; the other disk remained asleep with unchanged
counters. The test stopped that daemon, unmounted the target and returned the
disks to standby. This checks cron invocation, not production orchestration of
mounting, backup and spindown. The normal cron service remains stopped.

An SSH attempt restricted to password and keyboard-interactive authentication
was rejected with `Permission denied (publickey)` and exit 255.

A bounded 15-minute CPU load completed with 45 samples, a maximum of 68.933 C
and no reported fan-service fault. An independent time limit and an 80 C abort
check protected the run. After cooling, the CPU read 52.296 C; both disks were
in standby and PHY thermal monitoring remained enabled under `user_space`.

The identified fan worker was then stopped with SIGSTOP. The supervisor
replaced it within twelve seconds; status reported full fan state 3 and no
fault. Six seconds later that state was unchanged. This tests a stalled worker,
not a mechanical fan failure or disconnected sensor.

The remaining checks in the hardware protocol are still open. In particular,
this run does not establish repeated cold-start reliability, sustained memory
and concurrent I/O stability, physical enclosure functions, malformed-companion
recovery, or unattended scheduling. No public release gate is claimed passed.
