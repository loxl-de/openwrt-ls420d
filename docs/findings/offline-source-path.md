# Offline rebuild at the original source path

The archived candidate was rebuilt without network access or compiler cache in
[run 34731496493](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34731496493).
All three products match the original build byte for byte:

| Product | SHA-256 |
| --- | --- |
| `uImage.buffalo` | `5a64639273741c984cf08d8e243360c30c7b6d8240826e1a68a14bd7a7d2e54d` |
| `initrd.buffalo` | `3d89a914514042cb57e92f5e76b855b61fddba1dcb75dc3b61bce3fd57272354` |
| `packages.manifest` | `ddc19fc2c2fe663ad78df18dbfc158b90aef4d68eab63c9bfdeeacca6868ba8f` |

The normalized kernel configuration also matches. The source project commit was
`9b2ebcaaa95bcaa8a3714987fc5d475479b10226`; the diagnostic workflow commit was
`46d38ec204d0ddcacad531e33b52497173b00f01`.
Source artifact `10305461395` had ZIP SHA-256
`b3e41df02067ec9d4ae1ca0f1fde4b9cff4ca3c6baf30e3c3a4d0a5e0108ba0b`.

## What changed

The previous [offline run](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34721459238)
compiled and packaged successfully, but four payloads differed: `iperf3`,
`libiperf.so.0.0.0`, `libelf-0.192.so` and `libstdc++.so.6.0.33`.
The APK database reflected those differences; the example companion already matched.

The successful run restored the same archive at
`GITHUB_WORKSPACE/openwrt-src`, matching the online source path, instead of
`RUNNER_TEMP/offline-source/openwrt`. Four jobs, network isolation and disabled
compiler cache were retained. Diagnostic collectors ran after compilation.
All four payloads now match the canonical files, including their complete SHA-256,
ELF segment hashes, build IDs where present, and source-path fingerprints.
The canonical `libstdc++` contains seven absolute build paths.

This establishes a working fixed-path rebuild for this archived candidate.
It does not establish reproducibility across arbitrary paths, repositories or
runner images, nor isolate every compiler-level cause: the two runs used separate
runner instances, and the earlier run lacked equivalent build-input diagnostics.

## Using the verified path

The offline workflow defaults `same_workspace_path` to `true`. It moves only the
verified source directory and refuses an occupied or symlinked destination.
Set the input to `false` only for a deliberate different-path comparison.
When reproducing an artifact from another repository layout, preserve its original
absolute build path; matching a different checkout's default path is not sufficient.

Evidence artifact `10310334444` contains the product comparison, kernel-config
comparison, rootfs inventory, ELF fingerprints and build-input fingerprints.
It expires on 2026-09-27; retain the reports before then. It contains no firmware.
This build result does not grant firmware distribution approval or complete the
separate licensing review. No NAS deployment was changed for this experiment.
