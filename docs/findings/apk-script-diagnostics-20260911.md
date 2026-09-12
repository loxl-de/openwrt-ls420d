# APK script archive diagnostic failure

## Initial diagnostic

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

## Confirmed duplicate member and occurrence-aware evidence

Run [34600753826](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34600753826)
at `771a7d825a2d69f57a927d3e31ca27f7d22bbca9` identified the rejected
condition: duplicate name at zero-based member index 278. The entry was a
regular file, 165 bytes long, with an 85-character name and no PAX fields.
This failure was not another filename-syntax rejection.

Commit `b679f4cbafd25967a98e958360798802c3b01eb9` changes the diagnostic
inventory to script-evidence schema 2. Each name maps to an ordered list of
all its occurrences. The report also records the total member count and
duplicate-name counts. An earlier occurrence cannot be silently overwritten
by a later one, even when their contents match.

The inventory retains content and metadata hashes for every occurrence,
the name-order hash, the uncompressed archive hash and the gzip header.
The rootfs inventory still hashes the original compressed file. No archive
is extracted to disk, rewritten, sorted or deduplicated. Type, path, PAX and
size checks remain; the 4096-member bound counts occurrences, not unique names.

This permits diagnosis of the repeated entries. It does not establish that
the duplicates are correct, why they were produced, or whether they explain
the differing package databases.

The change passed 121 Python tests and 15 shell tests. Regression cases cover
identical, changed and reordered duplicates, occurrence limits and an
integration check that the archive bytes and original file hash stay unchanged.

Independent comparison
[34608937035](https://github.com/loxl-de/openwrt-ls420d/actions/runs/34608937035)
uses this evidence format. Compare the installed database's field and order
hashes separately from the script occurrence lists before proposing a fix.
OpenWrt's pinned rootfs preparation uses `gzip -9n`; ordinary gzip header
timestamps should not be assumed to explain the mismatch. The actual headers,
tar metadata and payload hashes remain part of the comparison.
