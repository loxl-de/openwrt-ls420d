"""Execute the patched version-check recipe under concurrent make processes."""
import concurrent.futures
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ToolchainLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ls420d-toolchain-lock-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        patch = (ROOT / "openwrt/patches/110-serialize-toolchain-version-check.patch").read_text()
        lines = [line[1:] for line in patch.splitlines()
                 if line.startswith((" ", "+")) and not line.startswith("+++")]
        start = next(i for i, line in enumerate(lines) if "/stamp/.ver_check:" in line)
        stop = next(i for i in range(start + 1, len(lines)) if not lines[i].strip())
        rule = "\n".join(lines[start:stop]).lstrip()
        variables = {"TOPDIR": self.root, "TMP_DIR": self.root / "tmp",
                     "TOOLCHAIN_DIR": self.root / "tc", "BUILD_DIR": self.root / "build",
                     "STAGING_DIR": self.root / "stage", "BUILD_DIR_TOOLCHAIN": self.root / "tc-build"}
        self.makefile = self.root / "fixture.mk"
        self.makefile.write_text("".join(f"{k}:={v}\n" for k, v in variables.items()) + rule + "\n")
        (self.root / "tmp").mkdir()
        (self.root / "tmp/.build").touch()
        (self.root / "toolchain").mkdir()
        (self.root / "toolchain/Makefile").write_text("fixture\n")
        self.run_git("init", "-q")
        self.run_git("add", "toolchain")
        self.run_git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                     "commit", "-qm", "fixture")
        self.stamp = self.root / "tc/stamp/.ver_check"

    def run_git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True)

    def make(self, env=None):
        return subprocess.run(["make", "-s", "-f", str(self.makefile), str(self.stamp)],
                              cwd=self.root, env=env, capture_output=True, text=True, timeout=30)

    def test_concurrent_checks_and_unchanged_stamp_preserve_build(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.make(), range(32)))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stamp.read_text(), self.run_git("log", "--format=%h", "-1", "toolchain"))
        sentinel = self.root / "build/sentinel"
        sentinel.parent.mkdir()
        sentinel.touch()
        os.utime(self.root / "tmp/.build", (2000000000, 2000000000))
        self.assertEqual(self.make().returncode, 0)
        self.assertTrue(sentinel.exists())

    def failure_environment(self, command):
        bindir = self.root / "bin"
        bindir.mkdir()
        stub = bindir / command
        stub.write_text("#!/bin/sh\nexit 42\n")
        stub.chmod(0o755)
        return dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ["PATH"])

    def test_git_failure_does_not_prepare_toolchain(self):
        self.assertNotEqual(self.make(self.failure_environment("git")).returncode, 0)
        self.assertFalse(self.stamp.exists())

    def test_lock_failure_does_not_prepare_toolchain(self):
        self.assertNotEqual(self.make(self.failure_environment("flock")).returncode, 0)
        self.assertFalse(self.stamp.exists())


if __name__ == "__main__":
    unittest.main()
