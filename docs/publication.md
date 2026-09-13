# Maintainer publication checks

For each source or binary release, review the exact revision and the material
GitHub will expose. The following checks complement the automated tests.

- Scan tracked content and reachable history for credentials, private paths,
  device dumps and unintended account identity. Commit metadata, PRs, logs and
  release assets are separate surfaces. Preserve third-party attribution.
- Use only standard GitHub-hosted runners for public PRs. Do not expose private
  networks, deployment credentials or self-hosted runners to untrusted code.
- Keep workflow tokens read-only except in the manually dispatched candidate
  retention job. Require approval for outside contributors' workflows.
- Protect the default branch against deletion and force-pushes, require the
  actual CI checks, and use reviews appropriate to the available maintainers.
- Inspect Actions secrets, variables, deploy keys, webhooks and installations
  by purpose without copying their values into an audit.
- Confirm the private vulnerability-reporting route described in SECURITY.md
  and available secret-scanning/push-protection settings.
- Review asset retention and the paired-source requirements in
  [distribution.md](distribution.md) before publishing any firmware.
- Confirm the remote commit and asset hashes equal the reviewed candidate.
  A failed candidate job can leave an incomplete draft; never publish it.

Record inspected settings and inaccessible checks explicitly. An API permission
error is not evidence of a safe setting. Removing history does not revoke an
exposed credential or erase copies; rotate it first.

The original account migration is complete and is not a recurring release step.
Its earlier procedure remains in Git history. Repository cleanup does not change
visibility, permissions, release qualification or publish a draft.
