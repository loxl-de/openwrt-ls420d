# Copyright and license scope

The root `LICENSE` is the MIT license for original project scripts, runtime
files, tests and documentation, unless a file says otherwise. It does **not**
relicense OpenWrt, Linux, firmware packages or upstream code quoted in patches.

- `kernel-patches/301-preserve-initrd2-with-mangle.patch` modifies Linux code
  and is distributed under **GPL-2.0-only**. The original converter is marked
  `GPL-2.0` (the deprecated SPDX spelling for GPL-2.0-only).
- `openwrt/patches/100-add-buffalo-ls420d-ram-initramfs-support.patch` contains
  OpenWrt build/system changes and Linux driver context; distribute the combined
  patch under **GPL-2.0-only**. The new DTS retains its own
  **GPL-2.0-or-later OR MIT** alternative. These are not all MIT-only sources.
- The DTS includes the official LS421DE description by Daniel Gonzalez
  Cabanelas; its upstream copyright and license remain in the included file.
  LS420D hardware information credits Jeremy J. Peper, Steve Shih and Toha in
  the added DTS. Retain these third-party notices when preparing downstream work.
- OpenWrt's locked source contains its own `COPYING` and `LICENSES` directory.
  Linux and each selected package retain their respective notices and terms.

The GPL version 2 license text is supplied in `LICENSES/GPL-2.0`, copied
unchanged from the locked OpenWrt source. MIT is in the root `LICENSE`.

No vendor bootloader dumps, proprietary firmware, private site overlays or SSH
keys are licensed or distributed by this source repository. Legacy uImage
wrappers and the anonymous data-only example are constructed by original
MIT-licensed project code; the example is supplied with that license.

See [binary distribution policy](docs/distribution.md) before sharing compiled
images. This notice is a source attribution map, not a blanket license clearance
for arbitrary packages or user-provided files.
