# Security policy

This is experimental RAM-boot integration. **No version currently has a
supported production security lifecycle.** Do not expose the NAS directly to
the Internet or use it as the only copy of valuable data.

Never attach private companions, SSH keys, tokens, unredacted logs, disk
inventories or vendor configuration dumps to issues, PRs or Actions artifacts.
TFTP and legacy image CRCs are not authentication, encryption or secure boot.
Physical and boot-network access are part of the trust boundary.

Use GitHub's **Report a vulnerability** / private vulnerability reporting on
this repository when available. If that option is absent, open a content-free
issue asking the owner `loxl-de` to enable a private reporting channel. Do not
include exploit details or secrets in that request. No private contact address
or guaranteed response time is implied.

If a credential is exposed, revoke or rotate it first. Removing a file or
rewriting Git history does not revoke credentials or erase copies and PR refs.

Before accepting a firmware download, check its source revision, notices,
checksums, known limitations and hardware-validation status. A green example
job proves neither a successful kernel build nor a tested device.
