# Source publication and binary distribution

## Current enforced policy

Public source development and full compilation on standard GitHub runners are
enabled independently of firmware distribution. The workflow builds the complete
firmware, runs its packaging checks and uploads **text-only compile evidence**.
An explicit allowlist excludes all kernel/rootfs binaries. Reproducibility jobs
compare SHA-256 digests of the actual products built on independent runners.
This is a hash comparison, not a downloaded byte-for-byte comparison.

The separate anonymous data-only example companion is still downloadable. It
contains no kernel, executable OS, keys or operating configuration for a real
site. Its MIT license accompanies it. Nothing runs on the NAS from CI.

Firmware upload cannot be enabled with a dispatch input or repository variable.
It requires a reviewed workflow change implementing the source requirements
below. This is a temporary **distribution** gate, not a claim that a kernel
must be hardware-validated before its source can be public.

## Source inputs available for review

After a successful full build, CI also collects a source review candidate.
It contains the exact committed project, OpenWrt and feed trees, including
their build recipes, patches and license files. Separate archives contain the
downloaded source inputs. The resolved OpenWrt and Linux configurations,
package metadata, build manifest and runner information accompany them.

The collector excludes Git metadata, untracked worktree files and built
firmware. It refuses missing inputs, unexpected download entries and an
existing output directory. The SHA-256 inventory identifies every collected
download and every output file.

This candidate is preparation for review, not a declaration of complete source
availability or license compliance. A [clean offline rebuild](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34671908071)
has completed compilation and packaging with matching normalized kernel
configuration. Its kernel-image hash differs, so the reproducibility comparison
fails. That is not evidence of a missing source input. The temporary
14-day Actions artifact is not the long-term source offering required below.
The firmware-upload gate remains closed.

## Pair the artifacts with their sources

After collection, CI runs `scripts/stage-candidate.py` on the runner. It verifies
the source inventory, matches the build manifest and checks each product hash
before copying the two boot files and their sources into one candidate directory.
It checks the copies again before writing the outer `SHA256SUMS`.

For an existing local build and its collected sources:

```sh
python3 scripts/stage-candidate.py \
  --artifacts build/artifacts-a \
  --sources build/source-review-a \
  --output build/candidate-a
```

The output must not already exist. This step does not rebuild or upload anything,
change the source-review flags, or certify license compliance. A failed copy
may leave a partial directory without its final checksum inventory; do not use
that directory as a completed candidate. The current CI upload allowlists still
exclude the candidate's firmware files.

## Retain an unpublished candidate

The separate [candidate workflow](candidate-build.md) keeps the firmware,
matching sources and original notices in a release draft. It runs only when
started manually from the reviewed `main` branch. The draft is not published,
and a failed run can leave it empty or incomplete.

This retention path does not enable public firmware downloads. The ordinary
pull-request CI remains read-only and keeps its existing upload allowlist.
Public release still requires the checks below.

## Acceptance criteria for downloadable firmware

Before enabling any public kernel/rootfs download, including an experimental
Actions artifact, maintainers must validate the exact package set and provide:

1. The exact project revision, OpenWrt and feed sources, local changes, build
   and installation scripts. A commit hash is an identifier, not source content.
2. The source archives actually consumed by the build, including any generated
   or otherwise unavailable inputs, and the package-specific patches/recipes.
   A warm download cache must not conceal a missing source input.
3. The resolved OpenWrt and Linux configurations, package/version inventory,
   toolchain identity, build instructions and a source-to-binary manifest.
4. Relevant copyright notices, license texts and redistribution conditions
   for Linux and every selected package. Preserve third-party attribution.
5. Sources obtainable alongside the corresponding binaries for the period
   required by their licenses; do not rely on a short-lived CI artifact or
   someone else's mutable download URL as the sole source offering.
6. An independent offline-source rebuild check, using the supplied sources,
   distinguishing missing inputs and build failures from product-hash differences.
   Build reproducibility is checked separately; a matching hash alone does not
   validate license compliance.

This process should run on public standard GitHub runners. A sources bundle
may be larger than the firmware; budget storage and retention explicitly.
Keep source archives and firmware paired when publishing and retiring versions.
Do not use a bare promise of future source availability as a substitute.

Existing private experimental firmware is not part of the public source release.
Preserve it outside the public repository before retiring old GitHub artifacts,
or use a fresh source-only repository that does not inherit those artifacts.

## Scope of review

The project has not yet validated a complete corresponding-source bundle for
the new native build. Accordingly the CI gate remains closed. Local builds
remain possible, but anyone redistributing them must satisfy the same conditions.

Primary references: [OpenWrt licensing](https://openwrt.org/license),
[GPLv2 text](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html),
[GNU source distribution FAQ](https://www.gnu.org/licenses/gpl-faq.html#UnchangedJustBinary).

## Offline source test

The `Offline source rebuild` workflow accepts a source-review artifact ID from
this repository and the independently checked SHA-256 digest of its ZIP. It
verifies the ZIP and every member before restoring project, OpenWrt, feeds and
downloads into a new directory. Existing output is never overwritten. Archive
paths and symlinks must stay inside their source tree.

The test installs host dependencies before entering an empty network namespace.
Only loopback is activated inside that namespace: OpenWrt's fakeroot uses local
TCP for inter-process communication. A preflight check rejects external
interfaces or inactive loopback and tests a local TCP exchange before compiling.
A failed parallel build is repeated serially with verbose output for diagnosis;
the original failure remains a failure even if that diagnostic retry succeeds.

It then builds as the ordinary runner user, with no restored toolchain, compiled
objects or compiler cache. Feed indexing uses the archived feeds without fetching.
Both resolved configurations are checked against the original build. For the
Linux config, only the checkout-root prefixes in the two expected
CONFIG_INITRAMFS_SOURCE paths are rebased after validation. The rebuilt paths
must point into the actual offline checkout. Architecture suffixes, owner IDs
and all other configuration lines must still match. The ATAG
test and Buffalo packaging checks run again; the resulting kernel, example
companion and package manifest are compared with the original product hashes.

The archived OpenWrt `version` file supplies the revision string. A temporary
Git baseline permits patch application and reporting; it is not presented as
the original Git history. The result identifies the original source revision
from the verified bundle. It does not authorize firmware distribution or replace
the separate license review.

To test a workflow change before it is merged, dispatch the existing `CI`
workflow on that branch with `offline_source_artifact` and
`offline_source_sha256`. It calls the reusable offline workflow and skips normal
firmware compilation. A normal dispatch with `reproducibility=true` still runs
two independent online-source builds.

Only three explicitly named JSON diagnostics can be uploaded: the overall
result, the kernel-configuration comparison and the audited rootfs file
inventory. No file contents or rebuilt firmware are uploaded. A valid but
different kernel configuration permits diagnostic packaging and hashing, but
still makes the final result fail even if all product hashes happen to agree.
Invalid initramfs input paths stop the test before that diagnostic packaging.

[The first offline run](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34570805512)
failed during package building. After loopback was enabled for fakeroot,
[the replacement run](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34576303964)
completed full offline compilation on September 11. Its subsequent Linux-config
comparison failed first at CONFIG_RUSTC_VERSION, before Buffalo packaging.
Thus offline compilation is demonstrated; matching configurations and final
products are not.

[The diagnostic follow-up](findings/offline-rebuild-20260911.md) completed offline
compilation and packaging with matching kernel configurations. Its logs confirm
that sudo's default PATH hid rustc; preserving the runner PATH restored it.
The example companion and package manifest match, but the kernel-image hash
does not. This test used the original, pre-BUILDBOT source bundle. A new test
with the corrected build's sources is still required; the mismatch is not waived.
