# ADR 0002: Generic embedded root plus external configuration initramfs

Status: accepted design; native 25.12.5 hardware validation pending.

## Context

The LS420D needs a disk-independent RAM root, maintainable common builds and
private configuration updates without recompiling the operating system.
A post-boot loader adds ordering and availability dependencies. A permanently
personalized monolithic image couples unrelated updates and risks leaking keys.

## Decision

Build a generic kernel/DTB/embedded-root uImage in GitHub Actions. Restore the
standard ATAG_INITRD2 handoff while keeping OpenWrt's command-line policy.
Use a small external CPIO RAMdisk, expanded by Linux before init, for site data
and secrets. Publish only an anonymous, SSH-disabled example and its generator.

Keep generic code, site configuration and secrets under distinct custody.
They are not authenticated boot stages. No runtime loader, persistent overlay
or automatic flash writer is introduced.

## Evidence and consequences

A 25.12.2/Linux 6.12.74 hardware pilot demonstrated external configuration
reaching the running RAM root. The locked 25.12.5 native board build still needs
its own hardware checks. Host tests check archive construction, failure-closed
defaults, fan policy and ATAG conversion, not actual hardware.

Configuration-only changes need no kernel build. Credentials remain in a local
artifact, but TFTP exposes it to the boot network. Missing provisioning disables
SSH, so recovery must be established before deploying a candidate.
