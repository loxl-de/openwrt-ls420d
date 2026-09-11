# APK script archive diagnostic failure

Comparison [34594804028](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34594804028)
failed in the rootfs audit at commit
`1178d2dea2c754183dbd1ee88f266655f85005ac`. The firmware jobs did not produce
the requested field-level evidence. The previous tilde correction did not
resolve this failure.

The exception combined six checks: member type, PAX headers, filename syntax,
duplicate names, member size and member count. Its text did not identify which
check failed. Do not classify this second failure as the already-fixed tilde
case or infer another firmware defect from it.

The pinned APK 3.0.5 source writes script entries in `src/database.c`, in
`apk_db_scriptdb_write`. Names contain the package, version, checksum and script
action. `src/tar.c` writes regular entries and GNU long-name extension records
when needed. OpenWrt's `include/rootfs.mk` subsequently extracts and removes
post-install scripts, then recompresses the archive.

An existing local OpenWrt 25.12.2 script archive with 601 members passes the
current parser. This tests a real older archive, not the failed 25.12.5 output.
The latter was not uploaded and is not available for direct local inspection.
Neither check establishes which new member is rejected.

The diagnostic now reports the failed checks, member index, hashed name,
name length, type byte, size and PAX-field count. It does not print rejected
names, PAX values or script contents. All six rejection conditions remain in
place; product hashes and distribution restrictions are unchanged.

Regression tests cover the redacted error context, PAX rejection and a GNU
long script name. A new CI run is still needed to identify the actual failing
condition. This change improves the evidence; it is not claimed as a fix for
the archive failure or the two differing APK databases.
