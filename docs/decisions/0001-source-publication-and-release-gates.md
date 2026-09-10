# Decision 0001: separate source publication from firmware release

- **Status:** accepted
- **Date:** 2026-08-31

## Context

Public source enables review and allows the project to use the standard free
GitHub-hosted runner allocation for public repositories. Repository visibility
does not make an experimental firmware image safe or supported.

The source tree contains no private keys, device dumps, credentials, personal
storage inventories, private URLs, or operational Homelab configuration. Those
inputs remain in the private deployment repository or are provisioned outside
the build.

## Decision

The source repository may become public after a dedicated secrets, privacy,
license, and provenance audit. Public GitHub Actions is the canonical build
environment for the complete pinned OpenWrt source build.

Firmware publication is a separate gate. At the source-publication stage CI
uploads only text-only compile evidence and the anonymous data-only companion.
Kernel/rootfs downloads require the corresponding-source and licensing review
in [the distribution policy](../distribution.md), even for experimental output.
No CI artifact is an installation instruction or a hardware-support claim.
No GitHub Release and no claim of support or installability is permitted until
the hardware, recovery, persistence, and security gates in the roadmap pass.

## Consequences

- Review and CI may happen publicly before hardware support is complete.
- Every workflow artifact must be treated as untrusted experimental output.
- Device-specific keys, network settings, storage identities, and backup jobs
  are provisioned separately and never enter this repository.
- Validated releases are retained as GitHub Releases; short-lived Actions
  artifacts are not the release archive.
- A publication audit is repeated before the first release even if the source
  repository is already public.
