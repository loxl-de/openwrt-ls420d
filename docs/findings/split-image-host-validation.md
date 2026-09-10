# Split-image host validation — 2026-09-10

This record covers source and host tests, **not a native 25.12.5 hardware boot**.

- Locked OpenWrt baseline: 25.12.5, commit
  `f0a60eee2fe051741c643ea6118718aae1ef17fb`.
- Linux 6.12.94 source archive matched the OpenWrt-pinned SHA-256:
  `e998a232b9418db3301cb58468e291a4f41d6ab8306029b30d991f56251dc8d2`.
- Official mvebu patch 300 followed by this project's INITRD2 patch applied
  with fuzz disabled. Line offsets were required; no context was discarded.
- The native ATAG harness compiled the actual patched converter and passed
  absent/present-initrd, command-line filtering and DT-memory-preservation tests.
- 32 Python tests passed: 13 companion, 13 fan, 6 public-rootfs/installation tests.
- 14 existing/extended shell regression tests passed.
- ShellCheck 0.8.0, YAML parsing and tracked-tree privacy checks passed locally.
  CI separately runs its pinned ShellCheck version.
- The example generator is deterministic, refuses output replacement, embeds
  no authorization or host key, and leaves normal-boot SSH disabled.

The full 25.12.5 toolchain/image build and hardware acceptance are separate
checks. The private-repository gate deliberately prevents an automatic heavy
build in response to this change. The lightweight example artifact does not
prove the generic kernel compiled.

## Source-publication hardening — later on 2026-09-10

- 46 Python tests and all 14 shell tests passed on the source candidate.
- New tests cover suppressed secret output, forced credential paths, symlinks,
  removed historical secrets and an allowlisted text-only artifact exporter.
- Gitleaks 8.30.1 history scan, tracked-tree audit, ShellCheck 0.8.0, YAML parsing
  and the native ATAG converter regression passed locally.
- The pinned scanner download was independently checksum-verified by its installer.
- Two anonymous examples were byte-identical; their SHA-256 was
  `b1fccacaa3a013e4bf03bc0a75253aac8538fa5072d113c0c3c5f1c887d87c8c`.
- GPLv2 text and an explicit attribution/license map accompany source patches.
- CI uploads no kernel/rootfs binary until the corresponding-source gate is met.

These results are host-side checks. The hardened candidate has not yet run on
GitHub or undergone a full native firmware build or hardware acceptance.
