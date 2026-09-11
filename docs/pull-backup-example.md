# Reference pull-backup job

This is the one worked example the repository promises: a nightly pull of a
directory from another host, with the disks asleep in between. It shows that
the generic image carries what a backup NAS needs (`rsync`, `hd-idle`,
`block-mount`, cron, an SSH client) and how a configuration made on the
running system becomes part of the companion. It is not a finished appliance.

Everything below is done once on the running NAS over SSH, then captured with
`sysupgrade -b` and turned into the next companion as described in
[deployment](deployment.md). Interactive changes alone do not survive a reboot.

## 1. Mount the data volume at boot

Use the filesystem UUID so bay order does not matter:

```sh
uci add fstab mount
uci set fstab.@mount[-1].uuid="$(block info /dev/sda1 | sed -n 's/.*UUID="\([^"]*\)".*/\1/p')"
uci set fstab.@mount[-1].target='/mnt/backup'
uci set fstab.@mount[-1].enabled='1'
uci commit fstab
/etc/init.d/fstab boot
```

## 2. Let idle disks sleep

`hd-idle` ships disabled. Enable it for each data disk with a conservative
timeout; `hdparm -C /dev/sda` reports whether a disk is asleep:

```sh
uci set hd-idle.@hd-idle[0].disk='sda'
uci set hd-idle.@hd-idle[0].enabled='1'
uci set hd-idle.@hd-idle[0].idle_time_interval='20'
uci commit hd-idle
/etc/init.d/hd-idle enable
/etc/init.d/hd-idle restart
```

Anything that touches the mounted volume keeps a disk awake, including a
shell sitting in `/mnt/backup`. Write logs to RAM, not to the data volume.

## 3. A client key for the pull

The NAS initiates the connection, so it holds a client key and the source
host authorizes it. Restrict that key on the source to the one rsync command
it needs (`command="..."` in its `authorized_keys`) so a compromised NAS
cannot do more than read the backup source.

```sh
mkdir -p -m 0700 /root/.ssh
dropbearkey -t ed25519 -f /root/.ssh/id_ed25519 | grep '^ssh-ed25519'   # authorize this on the source
ssh -i /root/.ssh/id_ed25519 backup@source.example true                 # accept the source's fingerprint once
echo /root/.ssh/ >> /etc/sysupgrade.conf                                # include the key in backups
```

## 4. The job

One entry in root's crontab, run by the BusyBox cron that the base image
already starts. It is longer than a bare `rsync` call because four things
must hold before an unattended job is safe to leave alone:

- **The volume must be mounted and carry the marker file.** Without that
  guard a failed mount sends the whole transfer into the RAM root until
  memory runs out, which on a RAM-only system also takes the operating
  system down.
- **Only one instance may run.** A slow transfer that is still running when
  the next one starts would compete for the disk and the link. BusyBox
  `flock -n` refuses the second start instead of queueing it.
- **The result must be evaluated.** `rsync` exit status 0 is success; 23
  (some files could not be transferred) and 24 (files vanished on the
  source during the run) are partial results that deserve a look but not
  an alarm; everything else is a failure. Failures are logged at error
  priority, partial results at warning priority, so both stand out in
  `logread` and in a remote syslog receiver.
- **The status must be visible without reading logs.** The job writes its
  last outcome (`ok`, `warn` or `failed`), the status code and the time to
  a status file in RAM that a monitoring check on the source host can read
  over SSH.
- **Logs must stay bounded.** `rsync` prints one line per problem file; a
  bad night can produce thousands. Only the last 50 lines reach the log and
  the capture file is removed afterwards, so RAM cannot fill up with output.

```sh
mkdir -p /mnt/backup/data && touch /mnt/backup/.ls420d-volume
cat >> /etc/crontabs/root <<'EOF'
15 3 * * * flock -n /var/lock/pull-backup.lock sh -c 'if ! grep -qs " /mnt/backup " /proc/mounts || [ ! -f /mnt/backup/.ls420d-volume ]; then logger -p daemon.err -t pull-backup "volume not mounted, skipped"; echo "$(date -Iseconds) failed no-volume" > /var/run/pull-backup.status; exit 1; fi; /usr/bin/rsync -aH --numeric-ids -e "ssh -i /root/.ssh/id_ed25519" backup@source.example:/srv/data/ /mnt/backup/data/ > /var/run/pull-backup.log 2>&1; s=$?; tail -n 50 /var/run/pull-backup.log | logger -t pull-backup; rm -f /var/run/pull-backup.log; case $s in 0) r=ok; p=daemon.info;; 23|24) r=warn; p=daemon.warning;; *) r=failed; p=daemon.err;; esac; logger -p $p -t pull-backup "$r status $s"; echo "$(date -Iseconds) $r $s" > /var/run/pull-backup.status' || logger -p daemon.err -t pull-backup "previous run still active or volume missing, skipped"
EOF
/etc/init.d/cron restart
```

The transfer output goes to a file in RAM first and is logged afterwards,
because the exit status of `rsync | logger` would be that of `logger`; only
its tail is kept and the file is deleted. The
entry deliberately does not pass `--delete`. A mirror that follows
deletions also follows an accidental `rm` or a ransomware run on the source,
and then the backup is gone with the original. Keep deletions out of the
mirror, or keep history instead: `--link-dest` against the previous run
gives hard-linked daily snapshots at the cost of one directory per day. Add
`--delete` only after deciding that a mirror is what you want.

The disk wakes for the transfer and `hd-idle` puts it back to sleep once the
job is done. Run the entry by hand once, confirm `cat /var/run/pull-backup.status`
says `ok`, and check `logread -e pull-backup` before trusting the schedule.
A monitoring check on the source host can read that status file over SSH
and alert when it is older than a day, says `failed`, or says `warn` more
than once in a row.

## 5. Make it permanent

```sh
sysupgrade -b /tmp/backup.tar.gz
```

Copy that archive to the workstation and generate the companion from it. The
crontab, the fstab and hd-idle configuration and the client key are exactly
the data the backup route accepts. Test the new pair, then keep the previous
known-good companion until the first scheduled run has succeeded.

## What still needs measuring

Whether the disks really stay asleep between runs is a hardware result, not
a configuration property. Section F of the
[hardware test protocol](hardware-test-protocol.md) describes the 24 hour
standby measurement that closes this question.
