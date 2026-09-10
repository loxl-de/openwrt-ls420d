# Local LS420D bring-up evidence

This record separates observations made on the physical LS420D from design
assumptions. Private logs, flash/U-Boot dumps, keys, MAC addresses, and local
paths are deliberately not reproduced here.

## Proven on hardware

A complete OpenWrt 25.12.2 source build produced a U-Boot `uImage` containing
the kernel, the LS420D DTB, and an embedded uncompressed initramfs. It booted
entirely into RAM and provided SSH over the directly attached Ethernet link.
The running system reported the native primary identity `buffalo,ls420d`.

Inspection on that boot confirmed:

- both Armada SATA ports and the USB 2 host;
- the SPI-NOR partition map, including `u-boot-env` at `/dev/mtd1`;
- Ethernet and MAC selection from the preserved U-Boot environment;
- the RTC, GPIO fan, both temperature inputs, and all seven LEDs;
- the LS420D-specific absence of LS421DE NAND, SDIO, PCIe, and USB 3 hardware;
- the Marvell PHY advertises packet and magic-packet wake capability, and
  enabling magic-packet wake did not interrupt the active link.

The original U-Boot environment was saved outside this repository before the
tested environment change. Its contents and the device flash dump are recovery
material and must not be published.

## Input-event correction

The GPIO wiring from the community LS420D DTS was confirmed, but its generic
key codes caused OpenWrt's `gpio-button-hotplug` driver to reject the complete
`gpio_keys` device. The OpenWrt DTS therefore maps the power switch and function
button to `KEY_POWER` and `KEY_CONFIG`, and models the two disk-presence contacts
as `EV_SW` events using `BTN_0` and `BTN_1`. Event delivery still requires a
recorded hardware acceptance test.

## Historical failed fast repack and then-current rule (superseded)

A later diagnostic build reused an official precompiled kernel, appended the
LS420D DTB, and supplied a separately gzip-compressed RAM root. U-Boot fetched
both files after manual recovery activation, but the system never reached the
network. This does not disprove the standard precompiled-kernel-plus-DTB model.

The most likely cause is a format/configuration mismatch: the stock kernel had
`CONFIG_BLK_DEV_INITRD=y`, but no evidence of `CONFIG_RD_GZIP`; OpenWrt normally
selects external-initrd decompressors as part of an initramfs source build.
Without a serial log this remains a diagnosis, not a proven root cause.

At that stage the development artifact used the already successful
full source configuration: DTB plus uncompressed initramfs embedded in the
U-Boot kernel image. The old Buffalo bootloader's fake `initrd.buffalo` companion
was generated only for its filename contract. Reintroduction of a separate
external initrd was conditional on hardware evidence for its exact format and
kernel configuration. The subsequent split-image pilot below supplied that
mechanism evidence; the dummy companion is not the current architecture.

## Provenance

The hardware deltas were compared with Jeremy J. Peper's community LS420D DTS,
based on work by Steve Shih and Toha, at commit
`48084c9bb33a2ed9b6340969301c0265678d9d7d` of
[`1000001101000/Debian_on_Buffalo`](https://github.com/1000001101000/Debian_on_Buffalo/blob/48084c9bb33a2ed9b6340969301c0265678d9d7d/Trixie/device_trees/armada-370-linkstation-ls420d.dts).
Its dual license and author notice are preserved in the OpenWrt DTS patch.

## Subsequent split-image pilot (2026-09-10)

A later local OpenWrt 25.12.2 / Linux 6.12.74 pilot demonstrated the standard
external-initramfs path after preserving ATAG_INITRD2 under command-line
mangling. An external marker/configuration appeared in the running RAM root.
This supersedes the dummy companion as the intended deployment design; see
[ADR 0002](../decisions/0002-generic-kernel-external-initramfs.md).

This is historical mechanism evidence, **not** acceptance of the native
25.12.5 build. Private serial logs and personalized images are not published.
The repository contains the generic implementation and regression tests, not
those private deployment artifacts.
