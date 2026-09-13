# A private daily pull job

The optional `backup` object turns the companion into a single-job reference
setup: one SSH source, one Btrfs destination, once per day. The generic image
contains `ls420d-pull`; the companion contains only its configuration and keys.
No archive importer or post-boot download is involved. Without this object, no
backup job or data-volume mount is provisioned.

This example updates a current copy under `/mnt/backup/pull/`. It does not delete
files absent from the source, but it can overwrite files that changed there.
That is **not** version history or protection against ransomware. Choose a
snapshot/retention policy and prove a restore before treating it as your only
backup. Two independent destination disks and catch-up scheduling need a site
policy beyond this deliberately single-job example.

## Private inputs

Add this object to the private JSON described in [deployment](deployment.md):

```json
"backup": {
  "host": "source.example",
  "user": "backup",
  "source": "/srv/data/",
  "volume_uuid": "11111111-2222-4333-8444-555555555555",
  "hour": 3,
  "minute": 15,
  "client_key": "backup-client.dropbear",
  "host_public_key": "source-host.pub"
}
```

Replace the example UUID with the intended filesystem UUID, not a device name.
The source must be an absolute directory with a trailing slash; this first
schema accepts simple path components, not spaces or shell syntax. The schedule
uses the NAS system timezone (UTC unless changed). It is cron, not anacron:
missed runs while powered off are not caught up.

Generate a separate Dropbear Ed25519 client key with `dropbearkey -t ed25519 -f
backup-client.dropbear` in the private directory. Restrict it to mode 0600 and
install its public key on the source account. Restrict that account to the
required read-only source; it must have rsync installed and permission to read
the requested data and metadata. Do not reuse the NAS server host key.

`source-host.pub` is the source server's Ed25519 public host key, obtained and
verified through an independent trusted channel. It is one OpenSSH public-key
line, not an unverified `ssh-keyscan` result or a complete known_hosts file. The
generator binds it to `host` and removes comments. The client uses batch mode
and strict host-key checking: changed or unknown host keys fail the transfer.

The generated companion adds the client key and host pin under `/root/.ssh/`,
an explicit UUID mount at `/mnt/backup`, the job's UCI file and a fixed-command
root crontab. It contains recoverable credentials: never upload it to public
Actions or Releases. A trusted crontab is executable configuration even though
the archive contains no additional program files.

## Prepare and check the destination

The example does not format or repartition a disk. Before its first run, identify
the intended disk and filesystem, verify the mounted Btrfs UUID against the JSON,
then create `/mnt/backup/.ls420d-volume` containing that exact UUID and a newline.
Do this only after confirming `/mnt/backup` is the intended mounted volume;
do not create a marker on the unmounted RAM-root directory. Do not copy a marker
onto an unrelated volume to make a failed check pass.

`ls420d-pull` requires a writable Btrfs mount, the matching UUID reported by
`block info`, and the marker. Missing or wrong volumes fail before rsync. The
job holds its working directory on that filesystem and writes relative to it,
so detaching a mount cannot silently redirect the destination to RAM root.
A symlink at the `pull` destination is rejected. The destination must remain
under trusted local administration; these checks do not defend against root.

Run `/usr/sbin/ls420d-pull` manually first. Restore sample files elsewhere and
check ownership, ACLs and xattrs before leaving the daily schedule unattended.
The script neither changes standby timers nor unmounts the disk. Establish those
policies only after checking their interaction with cooling and monitoring.

## Failure and monitoring

A nonblocking lock prevents overlapping jobs. The last result is stored in RAM
at `/var/run/ls420d-pull/status`: `running`, `ok`, `warn` or `failed`, with a UTC
timestamp and a status code/reason. Exit 24 (source files vanished) is a warning;
23 (partial transfer) and other rsync failures are errors. The script preserves
the rsync exit code rather than the logger's code. Lock contention exits 75 and
does not overwrite the running job's status.

Only the last 8 KiB and at most 50 lines of transfer output reach syslog. The
temporary exit-status file is removed after the pipeline. Result state and local
logs disappear at shutdown; poll or forward them if durable history is required.
No automatic deletion or retention cleanup runs. Inspect failures and available
space, and complete the [24-hour standby and backup tests](hardware-test-protocol.md)
on the exact image before production use.
