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
        self.assertEqual(result['members']['fixture-1.abc.post-install'][0]['sha256'],
                         MODULE.digest(b'private-script-marker'))

    def test_openwrt_snapshot_version_in_script_name(self):
        name = 'base-files-1~f5dae5ece4.' + 'a'*40 + '.post-install'
        result = MODULE.scripts_evidence(archive([(name, b'fixture')]))
        self.assertIn(name, result['members'])
        self.assertEqual(result['members'][name][0]['sha256'], MODULE.digest(b'fixture'))

    def test_script_timestamp_and_order_are_visible(self):
        items = [('a.post-install', b'a'), ('b.post-install', b'b')]
        a = MODULE.scripts_evidence(archive(items, 1))
        b = MODULE.scripts_evidence(archive(items, 2))
        c = MODULE.scripts_evidence(archive(list(reversed(items)), 1))
        self.assertNotEqual(a['members']['a.post-install'][0]['mtime'], b['members']['a.post-install'][0]['mtime'])
        self.assertEqual(a['members']['a.post-install'][0]['sha256'], b['members']['a.post-install'][0]['sha256'])
        self.assertNotEqual(a['order_sha256'], c['order_sha256'])

    def test_duplicate_occurrences_are_preserved_without_payloads(self):
        result = MODULE.scripts_evidence(archive([('a', b'private-first'), ('a', b'private-last')]))
        self.assertEqual(result['schema'], 2)
        self.assertEqual(result['member_count'], 2)
        self.assertEqual(result['duplicate_names'], {'a': 2})
        self.assertEqual([entry['sha256'] for entry in result['members']['a']],
                         [MODULE.digest(b'private-first'), MODULE.digest(b'private-last')])
        self.assertNotIn('private-first', json.dumps(result))
        self.assertNotIn('private-last', json.dumps(result))

    def test_identical_duplicates_are_not_collapsed(self):
        a = MODULE.scripts_evidence(archive([('a', b'x')]))
        b = MODULE.scripts_evidence(archive([('a', b'x'), ('a', b'x')]))
        self.assertEqual(len(b['members']['a']), 2)
        self.assertNotEqual(a['member_count'], b['member_count'])
        self.assertNotEqual(a['order_sha256'], b['order_sha256'])
        self.assertNotEqual(a['uncompressed_sha256'], b['uncompressed_sha256'])

    def test_reordered_and_changed_duplicates_are_visible(self):
        a = MODULE.scripts_evidence(archive([('a', b'x'), ('a', b'y')]))
        b = MODULE.scripts_evidence(archive([('a', b'y'), ('a', b'x')]))
        c = MODULE.scripts_evidence(archive([('a', b'z'), ('a', b'y')]))
        self.assertNotEqual(a['members']['a'], b['members']['a'])
        self.assertNotEqual(a['members']['a'], c['members']['a'])
        self.assertNotEqual(a['uncompressed_sha256'], b['uncompressed_sha256'])
        self.assertNotEqual(a['uncompressed_sha256'], c['uncompressed_sha256'])

    def test_duplicate_limit_counts_occurrences_not_unique_names(self):
        result = MODULE.scripts_evidence(archive([('a', b'')] * 4096))
        self.assertEqual(result['member_count'], 4096)
        with self.assertRaisesRegex(ValueError, 'member-count-limit'):
            MODULE.scripts_evidence(archive([('a', b'')] * 4097))

    def test_unsafe_and_link_members_fail(self):
        for items in ([('../escape', b'x')], [('/absolute', b'y')]):
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

    def test_rejection_reports_reason_without_rejected_name(self):
        for items, reason, index in (
                ([('../private-marker', b'x')], 'name-format', 0),
                ([('safe', b'x'), ('../private-marker', b'y')], 'name-format', 1)):
            with self.subTest(reason=reason), self.assertRaises(ValueError) as raised:
                MODULE.scripts_evidence(archive(items))
            message = str(raised.exception)
            self.assertNotIn('private-marker', message)
            context = json.loads(message.split(': ', 1)[1])
            self.assertIn(reason, context['reasons'])
            self.assertEqual(context['index'], index)
            self.assertEqual(len(context['name_sha256']), 64)

    def test_pax_rejection_does_not_log_metadata(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w', format=tarfile.PAX_FORMAT) as tar:
            member = tarfile.TarInfo('fixture')
            member.pax_headers = {'comment': 'private-pax-marker'}
            tar.addfile(member)
        with self.assertRaises(ValueError) as raised:
            MODULE.scripts_evidence(gzip.compress(data.getvalue()))
        message = str(raised.exception)
        self.assertIn('pax-headers', message)
        self.assertNotIn('private-pax-marker', message)
        self.assertNotIn('comment', message)

    def test_gnu_long_script_name_is_supported(self):
        name = 'fixture-' + 'a' * 105 + '.post-install'
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w', format=tarfile.GNU_FORMAT) as tar:
            member = tarfile.TarInfo(name)
            member.size = 1
            tar.addfile(member, io.BytesIO(b'x'))
        result = MODULE.scripts_evidence(gzip.compress(data.getvalue(), mtime=0))
        self.assertIn(name, result['members'])

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
            scripts = archive([('fixture-1.abc.post-install', b'marker'),
                               ('fixture-1.abc.post-install', b'earlier-or-later')])
            (db/'scripts.tar.gz').write_bytes(scripts)
            output = base/'report.json'
            subprocess.run([sys.executable, str(repo/'scripts/audit-rootfs.py'),
                            str(root), str(output)], check=True, capture_output=True)
            result = json.loads(output.read_text())
            entry = result['lib/apk/db/installed']
            self.assertEqual(entry['sha256'], MODULE.digest(data))
            self.assertIn('fixture', entry['apk_details']['packages'])
            self.assertNotIn('marker', output.read_text())
            self.assertEqual(result['lib/apk/db/scripts.tar.gz']['sha256'], MODULE.digest(scripts))
            self.assertEqual((db/'scripts.tar.gz').read_bytes(), scripts)
            self.assertEqual(result['lib/apk/db/scripts.tar.gz']['apk_details']['member_count'], 2)

    def test_symlinked_database_parent_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'real').mkdir()
            (root/'lib').symlink_to(root/'real', target_is_directory=True)
            with self.assertRaises(ValueError):
                MODULE.database_evidence(root)


if __name__ == '__main__':
    unittest.main()
