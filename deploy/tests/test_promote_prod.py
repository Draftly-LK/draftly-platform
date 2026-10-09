"""Exercise promotion against disposable local Git repositories, never GitHub."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "promote-prod.sh"
BASH = os.environ.get("BASH_EXE", "bash")


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.remote = self.base / "remote.git"
        self.repo = self.base / "work"
        self.repo.mkdir()
        self.git("init", "--bare", str(self.remote))
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.git("remote", "add", "origin", str(self.remote))
        self.initial = self.commit("initial")
        self.git("branch", "prod")
        self.git("push", "origin", "main", "prod")

    def git(self, *args):
        return subprocess.run(
            [shutil.which("git"), *args],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def commit(self, name):
        (self.repo / f"{name}.txt").write_text(name, encoding="utf-8")
        self.git("add", f"{name}.txt")
        self.git("commit", "-m", name)
        return self.git("rev-parse", "HEAD")

    def promote(self, sha):
        return subprocess.run(
            [BASH, SCRIPT.as_posix()],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PROMOTION_SHA": sha},
        )

    def prod_tip(self):
        return self.git("ls-remote", "origin", "refs/heads/prod").split()[0]

    def test_fast_forward_promotes_exact_checked_commit(self):
        target = self.commit("feature")
        self.git("push", "origin", "main")
        result = self.promote(target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.prod_tip(), target)

    def test_already_synced_can_be_redeployed(self):
        result = self.promote(self.initial)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.prod_tip(), self.initial)

    def test_diverged_prod_is_not_overwritten(self):
        target = self.commit("feature")
        self.git("push", "origin", "main")
        self.git("checkout", "prod")
        hotfix = self.commit("hotfix")
        self.git("push", "origin", "prod")
        result = self.promote(target)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not an ancestor", result.stderr)
        self.assertEqual(self.prod_tip(), hotfix)

    def test_main_changed_during_ci_requires_new_run(self):
        self.commit("newer")
        self.git("push", "origin", "main")
        result = self.promote(self.initial)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("main changed", result.stderr)
        self.assertEqual(self.prod_tip(), self.initial)

    def test_invalid_sha_cannot_change_prod(self):
        result = self.promote("main; echo unexpected")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("40-hex", result.stderr)
        self.assertEqual(self.prod_tip(), self.initial)

    def test_main_advanced_after_fetch_is_not_promoted(self):
        newer = self.commit("newer")
        # Transfer the object without changing main until promotion's fetch ends.
        self.git("push", "origin", f"{newer}:refs/heads/race")
        shim = """
git() {
  command git "$@"
  local result=$?
  if [[ "$1" == fetch && "$result" == 0 ]]; then
    command git --git-dir="$RACE_REMOTE" update-ref refs/heads/main "$RACE_SHA"
  fi
  return "$result"
}
source "$PROMOTION_SCRIPT"
"""
        result = subprocess.run(
            [BASH, "-c", shim],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
            env={
                **os.environ,
                "PROMOTION_SHA": self.initial,
                "PROMOTION_SCRIPT": SCRIPT.as_posix(),
                "RACE_REMOTE": self.remote.as_posix(),
                "RACE_SHA": newer,
            },
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("main changed", result.stderr)
        self.assertEqual(self.prod_tip(), self.initial)


class ReleaseGuardTests(unittest.TestCase):
    def guard(self, expected, actual="a" * 40):
        return subprocess.run(
            [BASH, SCRIPT.with_name("check-release-sha.sh").as_posix()],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "EXPECTED_SHA": expected, "GITHUB_SHA": actual},
        )

    def test_matching_release_is_allowed(self):
        result = self.guard("a" * 40)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_manual_deploy_without_expected_sha_is_allowed(self):
        result = self.guard("")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_prod_changed_before_dispatch_is_rejected(self):
        result = self.guard("b" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("prod changed", result.stderr)

    def test_invalid_expected_sha_is_rejected(self):
        result = self.guard("prod")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("40-hex", result.stderr)


if __name__ == "__main__":
    unittest.main()
