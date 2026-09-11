# Create your own initrd.buffalo

This guide targets this repository's **external-initramfs-enabled** generic
`uImage.buffalo`. An arbitrary official OpenWrt image may ignore the companion.
The earlier zero-filled dummy RAMdisk is not this configuration archive.

## 1. Obtain and verify the generic build

At the source-publication stage, CI builds the firmware but uploads only
text-only compile evidence. There is **no downloadable generic kernel yet**;
see [the distribution gate](distribution.md). Do not try to boot an evidence
archive. The intended next step is a reviewed source-complete GitHub firmware
bundle; no mandatory local full build is introduced by this gate.

If you build locally using [the build guide](build.md), verify the generated
`SHA256SUMS` in the artifact directory with `sha256sum -c SHA256SUMS`. Once
binary uploads are enabled through review, do the same for a downloaded bundle.
Keep the source commit ID, build manifest and exact pair used for each test.

The separate lightweight example artifact contains only the anonymous companion,
this guide, the MIT license and checksums. It is not a full firmware build. Development artifacts
are not supported releases, and Actions retention is limited.

## 2. Inspect or regenerate the anonymous example

From the repository root, with Python 3:

```sh
python3 scripts/make_initrd.py --example --output build/example/initrd.buffalo
```

The generator creates parent directories but **refuses to overwrite an existing
output**. Choose a new output path for another candidate.

The example uses DHCP, hostname `ls420d-example`, no SSH keys and disabled SSH.
It contains only configuration data and a format 2 marker, not an init script
or a loader. The public JSON description is `examples/example.json`.
Do not expect to log in using a default root password.

## 3. Prepare private inputs locally

On a trusted Linux/WSL workstation, install Python 3 and the Dropbear key tool
(for example the distribution's `dropbear-bin` package). Then:

```sh
umask 077
mkdir -p private
cp examples/deployment.json private/site.json
ssh-keygen -t ed25519 -f private/admin
dropbearkey -t ed25519 -f private/dropbear_ed25519_host_key
chmod 600 private/dropbear_ed25519_host_key
```

These are **two different key pairs**:

- `private/admin` is the client private key. It stays on your workstation and is
  never put in the NAS image. Only `private/admin.pub` is authorized on the NAS.
  You may instead copy an existing trusted Ed25519 public key to that path, or
  several, one per line; comment lines and key comments are dropped.
- `private/dropbear_ed25519_host_key` is the NAS's private server identity.
  It goes into the private companion. Generate it once and preserve it securely
  so the NAS keeps a stable SSH fingerprint across reboots.

Do not generate a shared host key in public CI. Do not commit either private
keys or the completed private archive, even to this repository's private branch.
The ignored `private/` directory is a convenience, not a substitute for an audit.
Under WSL use a Linux filesystem (or correctly configured metadata support) for
private keys: Windows-mounted files may report permissive modes and will then
be rejected. You can keep the private directory outside the repository and pass
its JSON file by absolute path.

## 4. Customize and generate

Edit `private/site.json`. Paths to key files are relative to this JSON file:

```json
{
  "hostname": "ls420d-backup",
  "network": {"mode": "dhcp"},
  "ssh_public_key": "admin.pub",
  "dropbear_host_key": "dropbear_ed25519_host_key"
}
```

For a static IPv4 address replace the network object, for example:

```json
{
  "mode": "static",
  "address": "192.168.50.20/24",
  "gateway": "192.168.50.1",
  "dns": ["192.168.50.1"]
}
```

Use addresses appropriate to your network. These Linux settings do not change
U-Boot's TFTP addresses. The generator intentionally supports only this small
schema; arbitrary scripts, extra files, IPv6 provisioning and application secrets
are not accepted. Extend the schema and tests deliberately if needed.

```sh
python3 scripts/make_initrd.py --config private/site.json --output private/initrd.buffalo
sha256sum private/initrd.buffalo
```

The output is deterministic for identical inputs, including the same host key.
Changing configuration requires no kernel compile and no generic-image rebuild.
The private archive enables SSH on port 22 with public-key authentication only.
The generator checks framing/type and permissions of key inputs; it is not a
cryptographic key-validation service. Use valid keys from the stated tools.

## 5. Deploy the pair through an already validated boot path

Provide the generic `uImage.buffalo` and your private `initrd.buffalo` together
using your established SATA or TFTP boot arrangement. This guide does not
partition disks, change boot priority, flash U-Boot or modify its environment.
Do not adopt LS421DE NAND instructions.

A TFTP server holding the companion holds the NAS host private key in plaintext.
Restrict access to a trusted boot network. Merely placing the server on a home
LAN is not encryption or authentication.

With DHCP, find the lease and connect using the client key:

```sh
ssh -i private/admin root@ls420d-backup
```

Use the assigned IP if local name resolution is unavailable. Verify the server
fingerprint through your trusted provisioning records; do not blindly discard
a mismatch. Check `/etc/ls420d-deployment`, network settings, cooling, mounts,
and the [hardware acceptance checklist](hardware-test-protocol.md).

A missing or example companion leaves SSH disabled during normal boot.
This is not a claim that upstream physical-console/failsafe access is removed. Keep a known-good private
pair and a proven recovery route before trying a new one.

## Update lifecycle

- Site/key change: edit local inputs and generate a new companion under a new
  filename. Preserve the old known-good one until the new pair has booted.
- Common package/kernel/service change: reviewed source change, GitHub full
  build, checksums and tests, then test with a compatible private companion.
- Interactive changes and package installations affect RAM only and do not
  survive reboot. They are not an update mechanism.

The 25.12.2 pilot proved the mechanism. This repository's native 25.12.5 image
still needs hardware acceptance; neither the example artifact nor a green CI
badge constitutes that acceptance.
