# Contributing

Keep this a thin integration layer over pinned upstream OpenWrt. Submit small
reviewable PRs; do not import a vendor dump, private configuration or image.
Use a GitHub noreply commit address if you do not want your email public.
GitHub separately records PR authors and workflow actors; commit metadata alone
does not anonymize those activities.

Run the checks in [the build guide](docs/build.md). Tests must include failure
cases and never print secret fixtures. Changes to workflows, kernel/DTS patches,
provisioning or thermal safety need particular scrutiny. Preserve third-party
licenses and copyright notices; contributions follow each file's license.

Describe separately what was tested on the host, compiled by CI and observed
on real hardware. Record versions and whether a result came from the older
pilot or the native board build. Do not claim a firmware release is supported
because a template or unit test passed.

No CI job may flash a board, contact a private NAS, alter its boot environment,
or use a homelab/self-hosted runner for untrusted PR code. Use public standard
GitHub runners for compilation. Keep firmware distribution subject to
[the corresponding-source gate](docs/distribution.md).

Do not reopen the retired Debian/kexec experiments as the default architecture.
The present contract is the generic built-in RAM root plus a data-only external
companion, extracted by Linux before init, without a runtime loader.
