# Remaining work

The generic split-image candidate has booted on hardware and passed its recorded
reproduction checks. The next work is qualification and a usable backup
configuration, not another boot architecture.

1. Finish review of the exact candidate's paired sources, notices and release
   inventory. Source availability, reproducibility and hardware support are
   separate checks.
2. Complete qualification of the new `994e3c8` candidate. The
   [13 September record](findings/native-hardware-20260913.md) covers its actual
   pull job and restores on both disks, RAM root, MTD flags, enabled
   `user_space` PHY zone, load response, stalled-worker recovery and paired
   update/rollback. A 25-hour unmounted idle test and subsequent pull/restore passed;
   unattended scheduling and mounted-volume standby remain untested.
   Remaining checks include the missing marker, detach during transfer and
   protocol section F with the volume mounted as the companion mounts it.
   Check flash protection through MTD flags, never by writing test bytes.
3. Complete the cases the protocol still lacks on any image: repeated cold
   starts, sustained load, absent and malformed companion, and cooling
   failure handling with injected sensor and fan faults.
4. Qualify unattended scheduling and recovery beyond the synthetic fixture.
   Restores of ownership, ACLs and xattrs now pass on both test disks. The
   [reference job](pull-backup-example.md) remains a current-copy example;
   those tests do not add retention or prove production source permissions.
5. Carry the small downstream changes to newer pinned OpenWrt versions.
   Remove a workaround only when the corresponding upstream fix and regression
   test establish that it is no longer needed. Upstream submissions are useful,
   but not prerequisites for the present base system.

The existing release gate is unchanged: a supported firmware release requires
the full hardware protocol, demonstrated recovery, immutable build inputs,
documented two-image update/rollback and reviewed security and licensing.
A PARTIAL result does not pass that gate. An experimental-publication policy
would require a separate explicit maintainer decision; cleanup does not grant it.

After approval, retain checksums, manifests, test summaries and corresponding
sources with each release. Do not treat a short-lived Actions artifact as the
release archive.
