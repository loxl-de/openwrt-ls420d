# Prior-art index

This index prevents known leads and failed experiments from being lost. Inclusion
does not validate any LS420D hardware claim. Before a detail enters the DTS or an
image recipe, archive the exact revision consulted, its license and author notice,
the derived hypothesis, and LS420D test evidence in a separate finding.

| Source | Why it is indexed | Evidence status |
| --- | --- | --- |
| [`Debian_on_Buffalo` LS420D DTS at the reviewed commit](https://github.com/1000001101000/Debian_on_Buffalo/blob/48084c9bb33a2ed9b6340969301c0265678d9d7d/Trixie/device_trees/armada-370-linkstation-ls420d.dts) | Provides attributed LS420D hardware deltas from Jeremy J. Peper, based on Steve Shih and Toha. | Compared with the physical bring-up; retained deltas are documented in `local-bringup.md`. |
| [Official OpenWrt LS421DE support](https://github.com/openwrt/openwrt/tree/v25.12.5/target/linux/mvebu) | Neighbouring Armada reference in the selected upstream. | Official for LS421DE only; NAND, image/sysupgrade, PCIe and USB assumptions do not transfer. |
| [`rogers0/OpenLinkstation#2`](https://github.com/rogers0/OpenLinkstation/issues/2) | Reported boot attempt with unavailable networking/SSH. | Historical failure report; reproduce and preserve logs before drawing a cause. |
| [`Debian_on_Buffalo#47`](https://github.com/1000001101000/Debian_on_Buffalo/issues/47) | Hardware/bootloader and Ethernet-autonegotiation observations. | Prior-art hypotheses for MAC, naming and PHY tests, not confirmed LS420D support. |

The authoritative inputs for OpenWrt itself are the official OpenWrt repositories
and kernel/devicetree bindings. Third-party observations guide experiments only.
