# Remaining work

The generic split-image candidate has booted on hardware and passed its recorded
reproduction checks. The next work is qualification and a usable backup
configuration, not another boot architecture.

1. Finish review of the exact candidate's paired sources, notices and release
   inventory. Source availability, reproducibility and hardware support are
   separate checks.
2. Build a new candidate from `main` and re-run the acceptance checks that
   the NAS-base changes touch. The
   [current record](findings/native-hardware-20260912.md) covers `9b2ebca`,
   which predates rsync and `ls420d-pull`, the companion's volume mount, the
   `user_space` fan governor and standby-gated disk reads, the read-only
   SPI-NOR partitions and the router-package removal. On the new image:
   - the fan-bound thermal zones show `policy` `user_space` with `mode`
     `enabled` after boot, and one fan state change under load is observed;
   - a write to `/dev/mtd1` fails with EROFS, `fw_printenv` is absent, and
     `/proc/mtd` lists both partitions read-only;
   - the pull job runs end to end from a companion with the `backup` object,
     and a wrong `volume_uuid`, a missing marker and a detached mount each
     fail before rsync starts;
   - protocol section F is run with the volume mounted as the companion
     mounts it, because the recorded standby result was obtained with the
     disks unmounted.
3. Complete the cases the protocol still lacks on any image: repeated cold
   starts, sustained load, absent and malformed companion, and cooling
   failure handling with injected sensor and fan faults.
4. Prove a restore from the pull destination on the new image, not only the
   transfer: the [reference job](pull-backup-example.md) is a current-copy
   example until a restore of ownership, ACLs and xattrs has been checked.
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
