# Build and verify the generic image

The canonical build compiles pinned OpenWrt sources on a standard GitHub runner.
The public inputs are `openwrt.lock`, `feeds.lock`, `config/ls420d.config`,
the ordered source patches and `openwrt/files/`. Private configuration is
never needed to build the generic image.

## CI and candidate builds

Pull requests run host checks, generate the example twice, verify upstream
pins and compile one firmware copy. Main pushes and weekly checks build two
independent copies and compare product hashes. Manual dispatch can request
the same comparison. No device is contacted by CI.

Ordinary CI retains text-only compile evidence and collected sources. Use
[Retain candidate as draft](candidate-build.md) when the boot files must be
kept for a hardware test or release review. It stores paired sources and
firmware in an unpublished draft; it does not publish them.

Compiler cache is disabled for the verified CI build method. Only downloaded
sources are cached. The offline workflow tests reconstruction without either
network access or cached compilation; see [distribution.md](distribution.md).
No automatic serial retry doubles a failed offline build.

## Local host checks

From the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
./tests/test-scripts.sh
./scripts/audit-public-tree.sh
# Install pinned Gitleaks into a new temporary destination, then:
GITLEAKS=/path/to/gitleaks sh scripts/scan-secrets.sh
python3 scripts/make_initrd.py --example --output build/example/initrd.buffalo
```

Fan tests use BusyBox ash; native ATAG testing uses a C compiler and the actual
prepared kernel source. Run ShellCheck as in CI. The privacy checks inspect
tracked files and available Git history without printing matching secrets.
They do not inspect every GitHub log, artifact or PR metadata field.

## Full build

Use a clean committed checkout, the dependencies listed in the CI workflow,
sufficient disk space, and:

```sh
JOBS=4 ./scripts/build.sh
```

The build owns and cleans its marked OpenWrt checkout. Do not point it at a
tree containing other work. Packaging requires a fresh output location for
the companion. Prefer GitHub for compilation; local companion generation
needs Python, not the OpenWrt toolchain.

Install the host's `device-tree-compiler` package for `fdtget`. It validates
the compiled DTB; OpenWrt's toolchain still builds that DTB. An explicit
`FDTGET=/path/to/fdtget` override must work or the build fails before checkout
preparation.

## Checks that protect the boot contract

Packaging requires exactly one native LS420D kernel and package manifest.
It checks the board identity and that inherited PCIe, NAND and SDIO nodes are
disabled. The ATAG test checks external-initramfs forwarding while preserving
command-line filtering and the DT memory description.

The uImage must fit below the external companion's load address. A second
check measures the decompressed kernel, including its BSS reservation,
relocated decompressor and scratch margin. The distinction matters: a small
compressed download can expand over the companion during boot. XZ compression
of the embedded rootfs is part of the tested configuration, not an optional
diagnostic. The generator limits the external companion to 1 MiB.

These checks produce the two boot files, package and rootfs inventories,
upstream/source-overlay hashes, memory-layout figures and a build manifest.
They do not substitute for hardware testing. The
[delta guide](upstream-delta.md) explains the maintained patches and runtime
additions; the [hardware record](findings/native-hardware-20260912.md) records
what actually ran.
