import base64
import copy
import json
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from make_initrd import image
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

    def test_cli_refuses_overwrite(self):
        output = self.root/'initrd.buffalo'
        command = [sys.executable, str(ROOT/'scripts/make_initrd.py'), '--example', '--output', str(output)]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        before = output.read_bytes()
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(before, output.read_bytes())


if __name__ == '__main__':
    unittest.main()
