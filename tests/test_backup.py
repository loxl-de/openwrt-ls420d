from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_initrd as fixtures
ROOT = fixtures.ROOT

VOLUME = '11111111-2222-4333-8444-555555555555'


class BackupCompanionTests(unittest.TestCase):
    def setUp(self):
        fixtures.InitrdTests.setUp(self)
        client = self.root/'backup-client'
        client.write_bytes((self.root/'dropbear_ed25519_host_key').read_bytes())
        client.chmod(0o600)
        (self.root/'source-host.pub').write_text((self.root/'admin.pub').read_text())

    tearDown = fixtures.InitrdTests.tearDown
    entries = fixtures.InitrdTests.entries
    def job(self):
        return dict(host='source.example', user='backup', source='/srv/data/',
                    volume_uuid=VOLUME, hour=3, minute=15,
                    client_key='backup-client', host_public_key='source-host.pub')

    def test_backup_entries_and_rights(self):
        config = dict(self.config, backup=self.job())
        entries = self.entries(config)
        self.assertEqual(entries['etc/crontabs/root'].data,
                         b'15 3 * * * /usr/sbin/ls420d-pull\n')
        self.assertIn(VOLUME.encode(), entries['etc/config/fstab'].data)
        self.assertEqual(stat.S_IMODE(entries['root/.ssh'].mode), 0o700)
        for path in ('root/.ssh/backup_ed25519', 'root/.ssh/known_hosts',
                     'etc/crontabs/root', 'etc/config/ls420d-backup'):
            self.assertEqual(stat.S_IMODE(entries[path].mode), 0o600)
        pin = entries['root/.ssh/known_hosts'].data
        self.assertTrue(pin.startswith(b'source.example ssh-ed25519 '))
        self.assertNotIn(b'anonymous-comment', pin)
        self.assertEqual(entries, self.entries(config))

    def test_rejects_unsafe_or_unknown_job_fields(self):
        for field, values in {
            'host': ['-oProxyCommand=x', 'a;id', '*.example', ''],
            'user': ['-root', 'x;id', 'x\ny'],
            'source': ['/srv/../etc/', '/a//b/', '/a/./b/', '/a b/', '/srv/data'],
            'volume_uuid': ['not-uuid', ''], 'hour': [-1, 24, True, '3'],
            'minute': [-1, 60], 'client_key': ['', 'missing'],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    job = dict(self.job(), **{field: value})
                    self.entries(dict(self.config, backup=job))
        job = dict(self.job(), command='unexpected')
        with self.assertRaises(ValueError):
            self.entries(dict(self.config, backup=job))

    def test_source_pin_must_be_one_valid_public_key(self):
        key = self.root/'source-host.pub'
        original = key.read_text()
        for text in (original + original, 'source.example '+original, 'ssh-ed25519 invalid'):
            key.write_text(text)
            with self.assertRaises(ValueError):
                self.entries(dict(self.config, backup=self.job()))
        key.write_text(original)
        private = self.root/'backup-client'
        private.chmod(0o644)
        with self.assertRaises(ValueError):
            self.entries(dict(self.config, backup=self.job()))


class BackupRuntimeTests(unittest.TestCase):
    def run_job(self, status=0, mounted=True, marker=VOLUME, actual_uuid=VOLUME,
                locked=False, huge=False, symlink=False, marker_newline=True,
                block_line=None):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            volume = root/'volume'
            volume.mkdir()
            if marker is not None:
                (volume/'.ls420d-volume').write_text(marker + ('\n' if marker_newline else ''))
            if symlink:
                (volume/'pull').symlink_to(root)
            mounts = root/'mounts'
            mounts.write_text(f'/dev/sda1 {volume} btrfs rw,noatime 0 0\n' if mounted else '')
            runtime = root/'run'
            script = (ROOT/'openwrt/files/usr/sbin/ls420d-pull').read_text()
            script = script.replace('/var/run/ls420d-pull', str(runtime))
            script = script.replace('/mnt/backup', str(volume)).replace('/proc/mounts', str(mounts))
            stub = f'''\nuci() {{
 case "$*" in
  *main.host) echo source.example;; *main.user) echo backup;;
  *main.source) echo /srv/data/;; *main.volume_uuid) echo {VOLUME};;
  *) return 1;;
 esac
}}
block() {{ echo '{block_line or f'/dev/sda1: UUID="{actual_uuid}" TYPE="btrfs"'}'; }}
flock() {{ return {75 if locked else 0}; }}
logger() {{ if [ "$#" = 2 ]; then cat >>{root}/logged; fi; }}
rsync() {{
 printf '%s\\n' "$@" >{root}/args
 pwd >{root}/cwd
 {'awk ' + chr(39) + 'BEGIN {for(i=0;i<200000;i++) print "test-line"}' + chr(39) if huge else 'echo output'}
 return {status}
}}
'''
            command = script.replace('set -u', stub+'\nset -u', 1)
            result = subprocess.run(['busybox', 'ash', '-c', command],
                                    capture_output=True, timeout=15)
            read = lambda path: path.read_text() if path.exists() else ''
            return (result.returncode, read(runtime/'status'), read(root/'args'),
                    read(root/'logged'), read(root/'cwd'), (runtime/'rsync.rc').exists())

    def test_exit_status_and_bounded_logging(self):
        for code, state in ((0, 'ok'), (24, 'warn'), (23, 'failed'), (12, 'failed')):
            with self.subTest(code=code):
                result, status, args, log, cwd, leftover = self.run_job(code, huge=True)
                self.assertEqual(result, code)
                self.assertIn(f' {state} {code}', status)
                self.assertLessEqual(len(log.encode()), 8192)
                self.assertLessEqual(len(log.splitlines()), 50)
                self.assertIn('StrictHostKeyChecking=yes', args)
                self.assertNotIn('--delete', args)
                self.assertTrue(cwd.strip().endswith('/volume'))
                self.assertFalse(leftover)

    def test_marker_without_trailing_newline_is_accepted(self):
        code, status, args, _, _, _ = self.run_job(marker_newline=False)
        self.assertEqual(code, 0)
        self.assertIn(' ok 0', status)
        self.assertNotEqual(args, '')

    def test_empty_marker_is_rejected(self):
        code, status, args, _, _, _ = self.run_job(marker='', marker_newline=False)
        self.assertNotEqual(code, 0)
        self.assertIn('invalid-volume-marker', status)
        self.assertEqual(args, '')

    def test_uuid_match_is_exact_regardless_of_field_order(self):
        last_field = f'/dev/sda1: TYPE="btrfs" UUID="{VOLUME}"'
        code, status, args, _, _, _ = self.run_job(block_line=last_field)
        self.assertEqual(code, 0, status)
        self.assertNotEqual(args, '')
        for line in (f'/dev/sda1: UUID="{VOLUME}0" TYPE="btrfs"',
                     f'/dev/sda1: UUID="{VOLUME[1:]}" TYPE="btrfs"',
                     f'/dev/sda1: LABEL="{VOLUME}" TYPE="btrfs"',
                     '/dev/sda1: TYPE="btrfs"'):
            with self.subTest(line=line):
                code, status, args, _, _, _ = self.run_job(block_line=line)
                self.assertNotEqual(code, 0)
                self.assertIn('wrong-volume', status)
                self.assertEqual(args, '')

    def test_destination_and_lock_fail_before_transfer(self):
        for kwargs in (dict(mounted=False), dict(marker=None), dict(marker='wrong'),
                       dict(actual_uuid='wrong'), dict(locked=True), dict(symlink=True)):
            with self.subTest(kwargs=kwargs):
                code, status, args, _, _, leftover = self.run_job(**kwargs)
                self.assertNotEqual(code, 0)
                self.assertEqual(args, '')
                self.assertFalse(leftover)


if __name__ == '__main__':
    unittest.main()
