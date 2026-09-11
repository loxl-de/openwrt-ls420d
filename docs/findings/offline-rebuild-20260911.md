# Offline rebuild diagnostic, 2026-09-11

[Run 34583938051](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34583938051)
completed compilation and Buffalo packaging without external networking.
The final check failed because `uImage.buffalo` differs from the original.
The example companion and package manifest match.

This run deliberately used the original source bundle, before the BUILDBOT
configuration fix. It is not a test of the corrected configuration.

## Verified evidence

Artifact 10195110947 contains exactly the three expected JSON reports.
Its downloaded ZIP SHA-256 matches GitHub's recorded digest:
`4026137e8f20860fd672cc108f42f32ba3684cc3a38c7bf324efbdc03bb19d5b`.

The source ZIP SHA-256 is
`059db755f607a676db7e187f982466699ea47e2ebfa7b82461b03c352a272766`.
It identifies original project revision
`95f6e5745e663bfa12ccf034b459483efb8486de`.

| Product | Result |
| --- | --- |
| initrd.buffalo | Matches: b1fccacaa3a013e4bf03bc0a75253aac8538fa5072d113c0c3c5f1c887d87c8c |
| packages.manifest | Matches: ddc19fc2c2fe663ad78df18dbfc158b90aef4d68eab63c9bfdeeacca6868ba8f |
| uImage.buffalo | Original: 8d7631fb4ce3b891b745f31797b708a1bb10f2e32bcf183f92460393c28d25ff |
| uImage.buffalo | Rebuilt: a59273740f68f0510c1fe4f4e02fa32c6ee8c3f96f93f1ad323a16724074c868 |

The Linux configurations match after the existing validated checkout-root
rebasing. No compiler setting or other configuration field was ignored.
The job log records rustc 1.98.1 before isolation, no rustc under sudo's default
PATH, and rustc 1.98.1 again with the preserved runner PATH. This confirms that
the sudo environment hid that compiler. The preserved PATH fixes the observed
configuration mismatch.

## Remaining file differences

The original evidence did not record file-content hashes. As a diagnostic,
the offline inventory was compared with copy A of run 34577568680, a later
online build using the pre-BUILDBOT configuration. Both have 996 entries;
ten entries differ:

- etc/apk/keys/public-key.pem
- lib/apk/db/installed
- lib/apk/db/scripts.tar.gz
- lib/libubox.so.20260213
- lib/modules/6.12.94/gpio-button-hotplug.ko
- usr/bin/iperf3
- usr/lib/libelf-0.192.so
- usr/lib/libiperf.so.0.0.0
- usr/lib/libnl-tiny.so.1
- usr/lib/libstdc++.so.6.0.33

The first three paths also varied between the two online builds. The seven
binary differences have not been explained. This is a cross-revision comparison,
not proof of ten differences from the original image. In particular, the random
APK key alone cannot be claimed to explain the whole offline mismatch.

The next end-to-end test must use a verified source bundle from the corrected
independent build. If binary differences remain, inspect those files' build
paths, identifiers and sections before changing the build. Do not ignore their
hashes, inject synthetic source timestamps or weaken signature verification.
The distribution gate remains closed.
