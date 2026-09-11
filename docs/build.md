# Generic firmware build and CI lifecycle

## Canonical inputs

OpenWrt and all feeds are locked to exact commits. `config/ls420d.config`,
`openwrt/patches/`, `kernel-patches/` and `openwrt/files/` are the public
build inputs. No private configuration is needed.

The full OpenWrt source build is canonical. Local companion generation is
ordinary archive construction, not a kernel compile. An old ImageBuilder or
binary-repack experiment is not the release source.

## GitHub lifecycle

1. Review a source change in a pull request.
2. Run shell, Python, fan, privacy and upstream-lock checks.
3. Generate the anonymous example twice and compare bytes in a lightweight job.
4. On a public repository, run the full firmware job on a standard Ubuntu
   runner. While private, this heavy job requires explicit manual dispatch.
5. Prepare the owned upstream checkout, apply the native and kernel patches,
   install only public runtime files, resolve configuration and compile.
6. Check the actual ATAG converter, package the exact target products and
   publish allowlisted text-only evidence as development artifacts. Full firmware
   is built but not uploaded until the corresponding-source distribution gate
   is implemented and reviewed; see [distribution policy](distribution.md).
7. Public main pushes, scheduled checks and requested reproducibility runs
   compare independent full builds.
8. After binary-distribution review, generate a private companion locally,
   hardware-test the exact pair, then
   consider a separately reviewed firmware release.

The workflow does not deploy devices or publish GitHub releases. It does not
change repository visibility. Manual heavy builds of a private repository may
consume private Actions minutes; no paid larger runner is requested.

## Products built on the runner (not all uploaded)

- Generic `uImage.buffalo`: kernel, DTB and embedded RAM root.
- Anonymous `initrd.buffalo`: real external CPIO, no credentials, SSH disabled.
- Package manifest, rootfs path/type inventory, upstream delta and input hashes.
- Build manifest, SHA-256 checksums and runner provenance.

Only the anonymous example and the explicit text-only compile-evidence directory
are uploaded. Independent runs compare product hashes, not downloaded firmware
bytes. Firmware files stay on the ephemeral build runner. The distribution gate
does not disable public compilation or require an expensive local build.

See [the delta map](upstream-delta.md). CI refuses an ambiguous target artifact,
checks the native DTB, and enforces a kernel image below the 20 MiB gap between
the stock load addresses. The companion generator limits output to 1 MiB.
These checks do not replace a complete hardware memory-layout test.

## Local verification without a firmware compile

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
./tests/test-scripts.sh
./scripts/audit-public-tree.sh
# Install pinned Gitleaks into a new temporary destination, then:
GITLEAKS=/path/to/gitleaks sh scripts/scan-secrets.sh
python3 scripts/make_initrd.py --example --output build/example/initrd.buffalo
```

Fan tests need BusyBox with ash; full source tests also use a C compiler.
Run ShellCheck as in CI. The public-tree audit checks tracked files and selected
secret/identity patterns and fails closed on unreadable/symlinked/binary entries.
It never prints filenames or matching values. Gitleaks separately checks all
locally available Git refs, with scanner output suppressed. CI checks out full
history; neither check inventories remote PR metadata, logs or artifacts.
Tests include a secret removed in a later commit. These are defense-in-depth
checks, not a guarantee that arbitrary secrets are absent.

## Updating the OpenWrt pin

`scripts/bump-openwrt-lock.sh` looks up the newest point release of the
locked series (a new minor series is a deliberate decision, not a bump),
verifies that the tag peels to the listed commit, and rewrites `openwrt.lock`
and `feeds.lock` from that release's `feeds.conf.default`, keeping the mirror
URLs already chosen for the feeds. With `--check` it only reports. The
`lock-bump` workflow runs it weekly and opens a pull request on a
`bump/openwrt-<version>` branch after the script tests and the upstream
input verification have passed on the rewritten locks. Nothing floats: main
changes only when a maintainer has compared the proposal with the official
release announcement and merged it. The script tests read the expected
values from the lock files instead of hard-coding a commit, so a proposal
validates itself without a manual test edit.

The proposal branch is replaced only while every commit on it was authored
by the workflow's bot; as soon as a person pushes a correction to it, the
workflow leaves the branch alone and says so in its log, and the push uses
a lease against the branch head it inspected. An unchanged proposal is not
pushed again.

Two owner settings apply. The workflow needs "Allow GitHub Actions to create
and approve pull requests" under Actions permissions. A pull request opened
with the default workflow token does not trigger CI; set an optional
`LOCK_BUMP_TOKEN` secret (fine-grained, contents and pull-requests write on
this repository only) if you want CI to run on the proposal automatically,
otherwise close and reopen it once.

## Full build

Use the dependencies listed in `.github/workflows/ci.yml`, a clean committed
checkout, sufficient disk space and:

```sh
JOBS=4 ./scripts/build.sh
```

Prefer GitHub infrastructure for this expensive step. The build creates its
own marked OpenWrt checkout and cleans only that owned checkout on subsequent
runs. Do not point it at a working tree containing work you want to preserve.
The packaging stage refuses to overwrite an existing companion output; archive
previous artifacts outside the output directory before starting a fresh build.

The example-only CI job has no toolchain dependency and remains useful even
when a heavy build is gated. It must not be mistaken for proof that firmware
compiled. Hardware acceptance is tracked separately.
