"""Exercise the patched make expression with empty and populated version dates."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackageEpochTests(unittest.TestCase):
    def test_source_directory_selection(self):
        patch = (ROOT / 'openwrt/patches/120-ignore-empty-package-version-date.patch').read_text()
        added = next(line[1:].strip() for line in patch.splitlines() if line.startswith('+\t'))
        # The final two parentheses close the outer shell and DUMP condition.
        expression = added[:-2]
        with tempfile.TemporaryDirectory(prefix='ls420d-package-epoch-') as tmp:
            root = Path(tmp)
            source = root / 'package/system/mtd'
            source.mkdir(parents=True)
            (source / 'Makefile').write_text('fixture\n')
            build = root / 'build_dir/target/mtd'
            build.mkdir(parents=True)
            env = dict(os.environ, GIT_AUTHOR_DATE='@1782770622 +0000',
                       GIT_COMMITTER_DATE='@1782770622 +0000',
                       GIT_CEILING_DIRECTORIES=str(root / 'build_dir/target'))
            def git(*args):
                return subprocess.run(['git', *args], cwd=root, env=env,
                                      capture_output=True, text=True, check=True).stdout
            git('init', '-q')
            git('add', 'package')
            git('-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid',
                'commit', '-qm', 'fixture')
            makefile = root / 'fixture.mk'
            makefile.write_text(f'PKG_BUILD_DIR:={build}\nCURDIR:={source}\n'
                                f'SELECTED:={expression}\n'
                                "all:\n\t@printf '%s' '$(SELECTED)'\n")
            for content in [None, '', '1700000000\n']:
                with self.subTest(version_date=content):
                    if content is not None:
                        (build / 'version.date').write_text(content)
                    selected = subprocess.check_output(['make', '-s', '-f', str(makefile)],
                                                       cwd=root, env=env, text=True)
                    self.assertEqual(selected, str(build if content else source))
                    if not content:
                        self.assertEqual(git('-C', selected, 'log', '-1', '--format=%ct', selected).strip(),
                                         '1782770622')
            # This is why selecting the build directory for an empty file is wrong.
            blocked = subprocess.run(['git', '-C', str(build), 'log', '-1'], env=env,
                                     capture_output=True, text=True)
            self.assertNotEqual(blocked.returncode, 0)


if __name__ == '__main__':
    unittest.main()
