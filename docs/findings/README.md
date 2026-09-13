# Evidence worth carrying forward

Current evidence:

- [Hardware origin and older mechanism pilot](local-bringup.md).
- [Native candidate: boot, companion update and hardware limits](native-hardware-20260912.md).
- [Successful offline reproduction and the build-path limitation](offline-source-path.md).
- [Source provenance](source-review-25.12.5.md),
  [component notice review](runtime-notices-25.12.5.md) and
  [candidate release review](release-review-20260913.md).
- [Hardware references](prior-art.md).

Keep conclusions and the evidence needed to check them here. Large generated
inventories belong with the candidate's release assets. The small original
offline product/configuration verdicts remain in `offline-34731496493/`.

## Archived investigation

The complete pre-cleanup tree is retained at
[revision 8900f62](https://github.com/loxl-de/openwrt-ls420d/tree/8900f62/docs/findings).
It includes the APK duplicate-member investigation, intermediate non-reproducible
builds, the BUILDBOT experiment, initial host-only checks, detailed offline ELF
and toolchain fingerprints, and the generated 141-package release map.

Those records are historical evidence, not current blockers or instructions.
Their diagnostic tools and dedicated tests are recoverable from the same
revision. Removing them from the current checkout does not erase failed runs,
rewrite their results or change the firmware.
