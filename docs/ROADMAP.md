# Remaining work

The generic split-image candidate has booted on hardware and passed its recorded
reproduction checks. The next work is qualification and a usable backup
configuration, not another boot architecture.

1. Finish review of the exact candidate's paired sources, notices and release
   inventory. Source availability, reproducibility and hardware support are
   separate checks.
2. Complete the missing cases in the
   [hardware protocol](hardware-test-protocol.md): repeated cold starts,
   sustained load, companion failure/recovery and cooling failure handling.
   The [current record](findings/native-hardware-20260912.md) is partial.
3. Implement the small backup-ready extension described in
   [the base-system boundary](base-system.md), with private configuration kept
   in the companion and tested restore behavior.
4. Carry the small downstream changes to newer pinned OpenWrt versions.
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
