# Source-publication checklist

This is a release checklist, not a claim that owner settings have been applied.
Source visibility, successful compilation, binary redistribution and hardware
support are four separate acceptance decisions.

## Candidate content

- Scan the exact candidate's tracked files and complete reachable Git history.
- Check author/committer names and emails, tags and commit messages separately.
- Preserve third-party attribution and the license map in `NOTICE.md`.
- Run host tests, shell lint, YAML validation and the actual ATAG conversion
  regression. A new full firmware/hardware test remains a separate milestone.
- Keep only the canonical source branch; no private provisioning, images,
  device dumps, working directories or raw hardware evidence in the Git tree.
- Do not publish historical Actions binaries whose nested filesystems and
  corresponding sources have not been audited.

## Clean repository identity

The intended project identity is `loxl-de`. A clean initial commit is allowed;
preserve the previous development history in a private archive first. This is
not permission to remove upstream copyright or misattribute outside contributions.

Git commits are not the whole publication surface. GitHub retains PR authors,
reviews, event timelines, workflow actors, logs, artifacts and read-only PR refs.
A force-push or branch deletion does not rewrite those records. For strict
separation from an earlier personal account, prefer a **new empty non-fork
repository**, populated only with the reviewed source candidate, under the
intended account. Keep the old repository private as the development archive.
Do not copy its PRs, Actions history or Git mirrors to the new repository.

Create the destination, push and trigger CI with the intended account. Do not
add the former account as collaborator or create PRs through its connection.
If the old name must be retained, the owner can rename the old private archive
first and create a new empty repository with the intended name. That owner
operation needs an explicit name/permission decision; it is not automated here.

## Owner settings before public access / untrusted CI

- Keep the repository private until the final candidate and metadata review.
- Confirm GitHub-hosted standard runners only; no private-network/self-hosted
  runners available to untrusted workflows. Leave paid larger runners unused.
- Set default workflow token rights to read-only, and disable Actions PR approval.
- Require approval for all external contributors' workflow runs, not only the
  first contribution. Do not enable privileged execution of fork PR code.
- Inventory Actions secrets, variables, deploy keys, webhooks and installations
  by name/purpose only. The generic build needs no site credentials.
- Enable private vulnerability reporting and available secret-scanning/push
  protection. Confirm the reporting route promised by `SECURITY.md` works.
- Protect `main` against force pushes and deletion, require a PR and the actual
  static/upstream/example status checks. Configure required reviews appropriate
  to the available maintainers; an owner cannot independently approve their own PR.
- Validate rulesets/branch protection after making public if the plan does not
  expose those controls for private repositories. Pause Actions while any
  necessary protection for public contributions is unresolved.
- Review artifact/cache retention and billing budgets. The workflow's firmware
  upload gate must remain until source-distribution acceptance is complete.

Record which settings were actually inspected and their results in a private
handoff report; never substitute an API permission error for a safe default.

## Final transition

Confirm the remote commit equals the reviewed candidate, only intended branches
exist, all activity belongs to the intended project accounts, and there are no
unreviewed pre-existing artifacts, PR refs or metadata. The owner changes
visibility explicitly. Then verify protection and start the public full build.
Keep the kernel/rootfs upload gate; the anonymous example is independently usable.
Use [the hardware protocol](hardware-test-protocol.md) before claiming support.
