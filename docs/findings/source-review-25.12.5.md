# First source bundle review

The first successful native build is
[run 34539424333](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34539424333).
It tested merge commit `95f6e5745e663bfa12ccf034b459483efb8486de`, with
PR head `b11688ac8765bb76f40c6507814e3e80242109ae`.

The source-review ZIP is 615,636,609 bytes. Its verified SHA-256 is
`059db755f607a676db7e187f982466699ea47e2ebfa7b82461b03c352a272766`.
Every member checksum passed, and the new restoration tool successfully
restored the actual project, OpenWrt, feed and download archives.
This is a restoration result, not yet a completed offline rebuild.

The archived OpenWrt tree includes `version`, containing
`r33051-f5dae5ece4`. That avoids relying on an online Git checkout to recover
this revision string. The offline test preserves that file and indexes the
already restored feeds without updating them.

## Package declarations

The installed manifest contains 141 packages. After applying OpenWrt's ABI
suffix naming rule, 140 map unambiguously to the package metadata and all 140
have a license declaration. `libusb-1.0-0` maps to `libusb-1.0` with ABI `0`.
The kernel is the remaining package; its archived `COPYING` refers to GPL-2.0
and the Linux syscall exception, with additional per-file licensing rules.

For 56 packages, metadata does not specify `LicenseFiles`. This does not prove
that notices are absent from their sources. Those notices still need inspection
and inclusion in the materials accompanying any binary distribution. The
libusb archive's `COPYING` was checked separately. Toolchain runtime exceptions,
mixed-license packages and the host build sources also remain in review.

Generate the declaration inventory from a restored source bundle with:

```sh
python3 scripts/review-package-licenses.py /path/to/restored/bundle \
  --output /path/to/new-license-review.json
```

The inventory preserves upstream license strings. It does not convert a
declaration into a compliance verdict; all approval fields remain false.

## Outstanding release checks

The independent two-build comparison and network-isolated source rebuild are
in progress. Source artifacts currently expire after 14 days. Before publishing
firmware, complete notice review and provide durable, paired source and binary
downloads. A successful source build does not establish hardware compatibility.
The distribution gate remains unchanged.
