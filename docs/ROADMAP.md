# Roadmap and release gates

This is an evidence-driven plan. A phase is complete only when its exit criteria
are met and linked from a hardware test record. Passing CI alone is never proof
of hardware support.

## Phase 0 — Preserve and inventory

**Goal:** create a lossless baseline before changing the device.

- Inventory board revision, SoC, RAM, flash/storage, Ethernet PHY, SATA, USB,
  LEDs, buttons, fan, temperature sensors, and serial header.
- Save photos and full serial logs from the vendor boot process.
- Record bootloader version, environment, kernel command line, partition tables,
  `/proc/mtd`, block topology, and vendor device tree if obtainable.
- Import previous attempts under `docs/findings/` with provenance, commands,
  outcome, and an explicit hypothesis for each failure.
- Index known prior art in `docs/findings/prior-art.md`; treat every derived board
  detail as an unverified hypothesis until corroborated on LS420D hardware.
- Choose repository licensing before adding code, preserve upstream notices and
  SPDX identifiers, and record the origin of every copied or adapted contribution.
- Document a tested recovery route and create read-back backups before writes.

**Exit:** inventory and recovery documents have been reviewed; raw evidence is
retained; no unresolved ambiguity exists about which physical device is tested.

## Phase 1 — Pin upstream and produce a RAM-only image

**Goal:** boot a traceable OpenWrt initramfs without persistent writes.

- Re-verify the selected OpenWrt release against official release metadata when
  deliberately updating the versioned lock; never float automatically.
- Verify the exact core and external-feed commits from the machine-readable locks.
- Study the stable-branch LS421DE DTS and patches as references, separating
  shared Armada hardware from LS421DE-only NAND and PCIe/USB 3.0 assumptions.
- Add the minimal LS420D DTS and an explicit initramfs-only development profile.
- Emit checksums, source revision, configuration, patch list, compiler identity,
  and build timestamp alongside artifacts.

**Exit:** two clean builds are byte-identical where OpenWrt permits it; CI builds
the same inputs; the image reaches an OpenWrt shell over the tested Ethernet
path on real LS420D hardware without writing persistent storage.

## Phase 2 — Peripheral bring-up

**Goal:** validate the board description one subsystem at a time.

- Confirm CPU, RAM size, timers, watchdog, UART, Ethernet and stable networking.
- Confirm both SATA bays independently and concurrently using sacrificial disks.
- Test USB, LEDs, buttons, fan control, temperature reporting, RTC, and power-off.
- Exercise reboot and cold boot repeatedly; capture complete serial logs.
- Convert every result—including failures—into the test matrix.

**Exit:** mandatory tests in `hardware-test-protocol.md` pass, or a documented
limitation is accepted and prominently scoped.

## Phase 3 — Split-image deployment and rollback

**Goal:** validate the generic RAM image plus private external companion (ADR 0002).

- Verify the two-image layout and external initramfs handoff.
- Test example/missing companions (SSH disabled) and private key-only provisioning.
- Define configuration regeneration, pair compatibility and known-good rollback.
- Keep LS421DE NAND image recipes and sysupgrade code out of the LS420D path.
- Test power loss and deliberately invalid images with a proven recovery method.

**Exit:** generic update, configuration-only update, malformed/missing companion,
and rollback have been tested on hardware. Flash/sysupgrade remains unsupported.

## Phase 4 — Upstream readiness

**Goal:** make the port reviewable and sustainable.

- Split changes into small patches with rationale, preserved licensing, SPDX
  identifiers where applicable, provenance, and `Signed-off-by` trailers.
- Run the OpenWrt checks relevant to DTS, target definitions, image metadata,
  shell, and reproducible builds.
- Document the remaining downstream delta and prepare upstream submissions.
- Freeze a release candidate and repeat the full hardware protocol.

**Exit:** a fresh contributor can reproduce the image from the documented pin;
all shipped files have clear licenses; no undocumented binary blob is required.

## Phase 5 — Firmware release gate

The source repository may already be public under Decision 0001. A firmware
release, an installable label, or a support claim is allowed only when all of
the following are true:

- at least one named release candidate has completed the full protocol on a
  physical LS420D, with logs and checksums;
- recovery from a failed boot and interrupted upgrade has been demonstrated;
- CI rebuilds the candidate from an immutable source pin;
- two-image deployment and rollback are documented; unsupported flash/sysupgrade
  stays explicitly refused;
- known limitations, security implications, licenses, and support expectations
  are documented;
- secrets, device identifiers, private URLs, and redistributability problems
  have been removed in a dedicated release review.

After release approval, use signed tags and attach checksums, manifests,
test summaries, and source/build instructions to each release.
