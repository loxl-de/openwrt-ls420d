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

One line in root's crontab, run by the BusyBox cron that the base image
already starts:

```sh
cat >> /etc/crontabs/root <<'EOF'
15 3 * * * /usr/bin/rsync -aH --delete --numeric-ids -e 'ssh -i /root/.ssh/id_ed25519' backup@source.example:/srv/data/ /mnt/backup/data/ 2>&1 | logger -t pull-backup
EOF
/etc/init.d/cron restart
```

The disk wakes for the transfer and `hd-idle` puts it back to sleep once the
job is done. Run the line by hand once and check `logread -e pull-backup`
before trusting the schedule.

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
