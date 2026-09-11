# SPDX-License-Identifier: MIT
import gzip
import importlib.util
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'apk_evidence', Path(__file__).resolve().parents[1]/'scripts/apk_database_evidence.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def archive(entries, mtime=0):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for name, content in entries:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            member.mode = 0o755
            member.mtime = mtime
            tar.addfile(member, io.BytesIO(content))
    return gzip.compress(data.getvalue(), mtime=0)


class ApkEvidenceTests(unittest.TestCase):
    def test_only_package_names_and_hashes_leave_installed_database(self):
        data = b'P:fixture\nV:1\nT:private-description-marker\nC:checksum-A\n\n'
        result = MODULE.installed_evidence(data)
        self.assertNotIn('private-description-marker', json.dumps(result))
        self.assertNotIn('checksum-A', json.dumps(result))
        self.assertIn('fixture', result['packages'])

    def test_field_change_is_localized(self):
        a = MODULE.installed_evidence(b'P:fixture\nV:1\nC:aaa\n\n')
        b = MODULE.installed_evidence(b'P:fixture\nV:1\nC:bbb\n\n')
        left, right = a['packages']['fixture'], b['packages']['fixture']
        self.assertNotEqual(left['fields']['C'], right['fields']['C'])
        self.assertEqual(left['fields']['V'], right['fields']['V'])

    def test_field_and_package_order_are_not_hidden(self):
        a = MODULE.installed_evidence(b'P:a\nV:1\n\nP:b\nV:1\n\n')
        b = MODULE.installed_evidence(b'V:1\nP:a\n\nP:b\nV:1\n\n')
        c = MODULE.installed_evidence(b'P:b\nV:1\n\nP:a\nV:1\n\n')
        self.assertNotEqual(a['packages']['a']['record_sha256'], b['packages']['a']['record_sha256'])
        self.assertEqual(a['packages']['a']['sorted_lines_sha256'], b['packages']['a']['sorted_lines_sha256'])
        self.assertNotEqual(a['order_sha256'], c['order_sha256'])

    def test_duplicate_package_and_invalid_field_fail(self):
        for data in (b'P:a\n\nP:a\n\n', b'P:a\nmalformed\n\n',
                     b'P:../escape\n\n', b'P:a\n'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                MODULE.installed_evidence(data)

    def test_script_payload_is_hashed_not_exported(self):
        result = MODULE.scripts_evidence(archive([('fixture-1.abc.post-install', b'private-script-marker')]))
        self.assertNotIn('private-script-marker', json.dumps(result))
        self.assertEqual(result['members']['fixture-1.abc.post-install']['sha256'],
                         MODULE.digest(b'private-script-marker'))

    def test_script_timestamp_and_order_are_visible(self):
        items = [('a.post-install', b'a'), ('b.post-install', b'b')]
        a = MODULE.scripts_evidence(archive(items, 1))
        b = MODULE.scripts_evidence(archive(items, 2))
        c = MODULE.scripts_evidence(archive(list(reversed(items)), 1))
        self.assertNotEqual(a['members']['a.post-install']['mtime'], b['members']['a.post-install']['mtime'])
        self.assertEqual(a['members']['a.post-install']['sha256'], b['members']['a.post-install']['sha256'])
        self.assertNotEqual(a['order_sha256'], c['order_sha256'])

    def test_duplicate_unsafe_and_link_members_fail(self):
        for items in ([('../escape', b'x')], [('a', b'x'), ('a', b'y')]):
            with self.assertRaises(ValueError):
                MODULE.scripts_evidence(archive(items))
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w') as tar:
            member = tarfile.TarInfo('link')
            member.type = tarfile.SYMTYPE
            member.linkname = 'target'
            tar.addfile(member)
        with self.assertRaises(ValueError):
            MODULE.scripts_evidence(gzip.compress(data.getvalue()))

    def test_expansion_is_bounded(self):
        with self.assertRaises(ValueError):
            MODULE.scripts_evidence(gzip.compress(b'\0'*(MODULE.LIMIT+1)))

    def test_rootfs_audit_embeds_details_without_changing_file_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = Path(__file__).resolve().parents[1]
            root = base/'root'
            shutil.copytree(repo/'openwrt/files', root)
            db = root/'lib/apk/db'
            db.mkdir(parents=True)
            data = b'P:fixture\nV:1\n\n'
            (db/'installed').write_bytes(data)
            (db/'scripts.tar.gz').write_bytes(archive([('fixture-1.abc.post-install', b'marker')]))
            output = base/'report.json'
            subprocess.run([sys.executable, str(repo/'scripts/audit-rootfs.py'),
                            str(root), str(output)], check=True, capture_output=True)
            result = json.loads(output.read_text())
            entry = result['lib/apk/db/installed']
            self.assertEqual(entry['sha256'], MODULE.digest(data))
            self.assertIn('fixture', entry['apk_details']['packages'])
            self.assertNotIn('marker', output.read_text())

    def test_symlinked_database_parent_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'real').mkdir()
            (root/'lib').symlink_to(root/'real', target_is_directory=True)
            with self.assertRaises(ValueError):
                MODULE.database_evidence(root)


if __name__ == '__main__':
    unittest.main()
