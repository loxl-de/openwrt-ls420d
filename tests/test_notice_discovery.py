# SPDX-License-Identifier: MIT
import test_collect_notices as fixtures

MOD = fixtures.MOD


class DiscoveryTests(fixtures.NoticeTests):
    def inventory(self):
        return {'downloads': [{'name': self.source.name, 'sha256': MOD.digest(self.source)}]}

    def test_named_notice_without_manual_selection(self):
        selection = MOD.discover(self.root, self.inventory(), {'files': []})
        self.assertEqual(selection, self.selection)
        MOD.collect(self.root, selection, self.output)

    def test_selected_notice_not_duplicated(self):
        self.assertEqual(MOD.discover(self.root, self.inventory(), self.selection), self.selection)

    def test_duplicate_archive_inventory(self):
        inventory = self.inventory()
        inventory['downloads'] *= 2
        with self.assertRaises(ValueError):
            MOD.discover(self.root, inventory, self.selection)

    def test_source_not_in_inventory(self):
        with self.assertRaises(ValueError):
            MOD.discover(self.root, {'downloads': []}, self.selection)

    def test_conflicting_selected_notice(self):
        self.selection['files'][0]['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            MOD.discover(self.root, self.inventory(), self.selection)
