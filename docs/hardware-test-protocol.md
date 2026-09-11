# LS420D hardware test protocol

Copy this file to `docs/test-runs/YYYY-MM-DD-<device>-<revision>.md` for every
release-candidate run. Never overwrite an earlier run. Redact serial numbers and
network credentials before publication, while retaining a stable pseudonymous
device ID.

## Run identity

- Tester / date (UTC):
- Device pseudonym / board revision:
- Repository commit:
- OpenWrt commit and release:
- Artifact filename and SHA-256:
- Bootloader version and environment checksum:
- Serial settings and log path:
- Recovery method tested on:

## Preconditions

- [ ] Enclosure/board photos and inventory match this device ID.
- [ ] Vendor state, bootloader environment, and storage metadata are backed up.
- [ ] Recovery media/commands are locally available and were dry-run.
- [ ] UART input/output works; boot interruption is understood.
- [ ] Test disks contain no valuable data; all write targets are identified by
      model, serial (redacted in public copy), size, and current partition table.
- [ ] Artifact checksum and manifest match the repository commit.

## A. Non-destructive initramfs boot

- [ ] Load into RAM using the documented bootloader method.
- [ ] Confirm no persistent device was erased or written.
- [ ] Capture serial output from power-on through login.
- [ ] Record `/proc/cpuinfo`, `/proc/meminfo`, `/proc/iomem`, `dmesg`, device-tree
      compatibles, block devices, MTD devices, network links, and loaded modules.
- [ ] Recover to the documented known-good boot pair without unexpected writes.

## B. Core and networking

- [ ] Reported RAM matches the physical inventory; sustained memory test passes.
- [ ] Record the Ethernet MAC source, including whether U-Boot `eth1addr` is used;
      redact the value but retain a stable checksum for comparisons.
- [ ] Record SoC controller identity and Linux interface naming (including the
      prior-art hypothesis that controller `eth1` may appear as interface `eth0`).
- [ ] Preserve PHY registers/kernel logs; compare autonegotiation with a controlled
      forced-1000/full test, then run sustained bidirectional traffic and link-loss
      recovery. These are validation points, not known-good LS420D properties.
- [ ] Watchdog reset and clean reboot behave as documented.
- [ ] Ten cold boots and ten warm reboots complete without a new error signature.

## C. Storage and USB

- [ ] Bay 1 and bay 2 enumerate the intended physical disk consistently.
- [ ] Read/write/verify test passes on each sacrificial disk separately.
- [ ] Concurrent sustained I/O passes while monitoring errors and temperature.
- [ ] Hot-plug is tested only if electrically and mechanically supported.
- [ ] Every physical USB port enumerates low- and high-speed test devices.
- [ ] Determine USB-power GPIO polarity from measured behaviour before describing
      it as supported; record the safe initial and active states.

Record exact tools, durations, data sizes, hashes, kernel messages, and SMART data;
“works” without the command and evidence is not a passing result.

## D. Enclosure functions

- [ ] Each LED maps correctly; active-low behaviour is recorded.
- [ ] Each button produces the intended event, including long-press boundaries.
- [ ] Fan-control GPIO states and the alarm/fail indication are mapped and a safe
      fallback is tested. Claim RPM/tachometer measurement only if separately
      demonstrated by hardware evidence.
- [ ] Temperature sensors are plausible under idle and load.
- [ ] RTC retains time across power loss, if battery-backed.
- [ ] Power-off actually reaches a safe hardware state.

## E. Split-image deployment and rollback

- [ ] Record separate generic and companion SHA-256 values and kernel release.
- [ ] The private companion marker and configuration appear before services start.
- [ ] Example and absent companion cases do not expose SSH during normal boot.
- [ ] Private companion permits only the intended public-key SSH login.
- [ ] A configuration-only change boots with the unchanged generic image.
- [ ] Runtime root is RAM-backed; boot/data devices have no root-overlay dependency.
- [ ] Reboot discards uncommitted runtime configuration changes.
- [ ] CPU/fan fault handling works with this exact native DTS and kernel.
- [ ] HDD temperature monitoring does not defeat the intended disk sleep policy.
- [ ] Malformed companion failure and recovery to a known-good pair are recorded.
- [ ] No flash/sysupgrade operation is offered or required.

## F. Disk standby endurance

This section measures the core benefit of the RAM root; without it the
concept is not demonstrated. Mandatory for a release candidate.

- [ ] Configure the intended standby mechanism (`hd-idle` or drive firmware
      timer) and the intended monitoring, fan service and backup schedule.
- [ ] Sample `hdparm -C` for every data disk at least every 5 minutes for
      24 hours from a RAM-resident script that does not touch the volume;
      record timestamps and states.
- [ ] Count spin-ups. Every spin-up outside a scheduled job must be attributed
      to a cause (fan service, SMART query, mount access, filesystem
      background work) and either fixed or accepted with a documented reason.
- [ ] Record power draw at the wall if a meter is available, idle versus
      spinning.
- [ ] Pass criterion: no unattributed spin-up in 24 hours, and disks asleep
      for the whole interval between scheduled jobs minus the standby timeout.

## Result

- Overall: PASS / FAIL / PARTIAL
- Failed checks and issue links:
- Unexpected messages and log offsets:
- Persistent storage before/after comparison:
- Recovery exercise result:
- Tester sign-off:
- Independent reviewer:

A PARTIAL result never satisfies a release gate. Failed runs remain committed;
follow-up runs link back to them and state what changed.
