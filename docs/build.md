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
the stock load addresses. It also measures the decompressed kernel from the
`vmlinux` load segments: starting at the platform text offset, the kernel plus
`.bss`, the relocated decompressor and scratch space must end below the initrd
load address, otherwise the companion would be overwritten during boot. With
an uncompressed embedded initramfs that footprint is roughly the size of the
root filesystem; the check fails closed if the package set grows past the
limit, and its numbers (footprint, uImage size, scratch margin, worst-case
end, initrd load address and remaining headroom) are recorded in
`build.manifest` so the verdict can be reviewed against the hardware pilot
and so the decision whether to compress the embedded initramfs can rest on
measured headroom. The companion generator limits output to 1 MiB. These
checks do not replace a complete hardware memory-layout test.

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

## Full build

Use the dependencies listed in `.github/workflows/ci.yml`, a clean committed
checkout, sufficient disk space and:

```sh
JOBS=4 ./scripts/build.sh
```

Install the host's `device-tree-compiler` package for `fdtget`. Packaging uses
it only to read and validate the compiled DTB; OpenWrt still compiles the DTB
with its own toolchain. The build checks `fdtget` before preparing sources and
prints its version in the build log. Set `FDTGET=/path/to/fdtget` to override
the command found on `PATH`.

Prefer GitHub infrastructure for this expensive step. The build creates its
own marked OpenWrt checkout and cleans only that owned checkout on subsequent
runs. Do not point it at a working tree containing work you want to preserve.
The packaging stage refuses to overwrite an existing companion output; archive
previous artifacts outside the output directory before starting a fresh build.

The example-only CI job has no toolchain dependency and remains useful even
when a heavy build is gated. It must not be mistaken for proof that firmware
compiled. Hardware acceptance is tracked separately.
