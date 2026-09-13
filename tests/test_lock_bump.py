"""Offline update and proposal tests; no real remote or GitHub writes."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LockBumpTests(unittest.TestCase):
    def test_end_to_end_rewrites_the_pair_without_clobbering_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            upstream = base/'upstream'
            upstream.mkdir()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(upstream), *args], text=True).strip()
            git('init', '-q')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            feeds = []
            for index, line in enumerate((ROOT/'feeds.lock').read_text().splitlines()):
                if line.startswith('#') or not line:
                    continue
                name, url, _ = line.split('|')
                feeds.append((name, url, str(index % 9 + 1)*40))
            (upstream/'feeds.conf.default').write_text(''.join(
                f'src-git {name} {url}^{sha}\n' for name, url, sha in feeds))
            git('add', 'feeds.conf.default')
            git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'Fixture release')
            git('-c', 'tag.gpgsign=false', 'tag', '-am', 'Fixture tag', 'v25.12.10')
            commit, tag = git('rev-parse', 'HEAD'), git('rev-parse', 'v25.12.10')
            project = base/'project'
            (project/'scripts').mkdir(parents=True)
            for name in ('lib.sh', 'bump-openwrt-lock.sh'):
                shutil.copy(ROOT/'scripts'/name, project/'scripts'/name)
            shutil.copy(ROOT/'feeds.lock', project/'feeds.lock')
            url = 'https://example.invalid/openwrt.git'
            (project/'openwrt.lock').write_text(
                'OPENWRT_VERSION=25.12.4\nOPENWRT_TAG=v25.12.4\n'
                f'OPENWRT_TAG_OBJECT={tag}\nOPENWRT_COMMIT={commit}\n'
                f'OPENWRT_SOURCE_URL={url}\nOPENWRT_FALLBACK_URL={url}\n')
            env = dict(os.environ, GIT_CONFIG_COUNT='1',
                       GIT_CONFIG_KEY_0=f'url.{upstream.as_uri()}.insteadOf',
                       GIT_CONFIG_VALUE_0=url)
            command = ['sh', str(project/'scripts/bump-openwrt-lock.sh')]
            before = [(project/name).read_bytes() for name in ('openwrt.lock', 'feeds.lock')]
            result = subprocess.run(command+['--check'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('UPDATE_AVAILABLE=25.12.10', result.stdout)
            self.assertEqual(before, [(project/name).read_bytes() for name in ('openwrt.lock', 'feeds.lock')])
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            lock = (project/'openwrt.lock').read_text()
            self.assertIn(f'OPENWRT_COMMIT={commit}\n', lock)
            self.assertIn(f'OPENWRT_TAG_OBJECT={tag}\n', lock)
            self.assertIn('OPENWRT_VERSION=25.12.10\n', lock)
            for name, feed_url, sha in feeds:
                self.assertIn(f'{name}|{feed_url}|{sha}\n', (project/'feeds.lock').read_text())
            after = [(project/name).read_bytes() for name in ('openwrt.lock', 'feeds.lock')]
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('UP_TO_DATE=25.12.10', result.stdout)
            self.assertEqual(after, [(project/name).read_bytes() for name in ('openwrt.lock', 'feeds.lock')])

    def test_existing_proposals_are_never_overwritten(self):
        workflow = (ROOT/'.github/workflows/lock-bump.yml').read_text()
        step = workflow.split('      - name: Open or update the proposal\n', 1)[1]
        command = step.split('        run: |\n', 1)[1]
        command = '\n'.join(line[10:] if line.startswith('          ') else line
                            for line in command.splitlines())
        for branch, opened, rejected, push, create in (
                (True, True, False, False, False),
                (True, False, False, False, True),
                (False, False, False, True, True),
                (True, False, True, False, False)):
            with self.subTest(branch=branch, opened=opened, rejected=rejected), tempfile.TemporaryDirectory() as temp:
                log = Path(temp)/'calls'
                stub = f'''git() {{
 printf 'git %s\\n' "$*" >>"$CALL_LOG"
 case "$1" in fetch) return {0 if branch else 1};; esac
 return 0
}}
gh() {{
 printf 'gh %s\\n' "$*" >>"$CALL_LOG"
 case "$*" in
  *'--state closed'*) {'echo 1' if rejected else ':'};;
  *'--state open'*) {'echo 2' if opened else ':'};;
 esac
}}
'''
                env = dict(os.environ, CALL_LOG=str(log), GH_TOKEN='fixture',
                           VERSION='25.12.10', GITHUB_REPOSITORY='example/project')
                result = subprocess.run(['bash', '-euo', 'pipefail', '-c', stub+command],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = log.read_text()
                self.assertEqual('git push ' in calls, push)
                self.assertEqual('gh pr create ' in calls, create)
                self.assertNotIn('--force', calls)
                if branch:
                    self.assertNotIn('git checkout ', calls)
                    self.assertNotIn('git commit ', calls)


if __name__ == '__main__':
    unittest.main()
