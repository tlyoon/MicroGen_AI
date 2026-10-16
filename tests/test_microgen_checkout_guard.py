"""Real Git checkout preflight tests; no external API or Drive access."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from microgen_batch import inspect_local_checkout


@unittest.skipUnless(shutil.which("git"), "Git executable required")
class CheckoutGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "checkout"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"],
                       check=True, capture_output=True)
        (self.repo / "file.py").write_text("print(1)\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "."],
                       check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.name=Fixture",
             "-c", "user.email=fixture@example.invalid", "commit", "-qm", "initial"],
            check=True, capture_output=True
        )
        self.sha = subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
            text=True
        ).strip()

    def test_clean_local_checkout_and_full_commit_pin(self):
        self.assertEqual(inspect_local_checkout(self.repo), self.sha)
        self.assertEqual(inspect_local_checkout(self.repo, expected_commit=self.sha), self.sha)
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            inspect_local_checkout(self.repo, expected_commit="0" * 40)
        with self.assertRaisesRegex(RuntimeError, "full 40-character"):
            inspect_local_checkout(self.repo, expected_commit="deadbee")

    def test_modified_untracked_or_missing_files_fail(self):
        (self.repo / "file.py").write_text("print(2)\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "dirty"):
            inspect_local_checkout(self.repo)
        subprocess.run(["git", "-C", str(self.repo), "restore", "file.py"],
                       check=True, capture_output=True)
        (self.repo / "untracked.txt").write_text("draft", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "dirty"):
            inspect_local_checkout(self.repo)
        (self.repo / "untracked.txt").unlink()
        (self.repo / "file.py").unlink()
        with self.assertRaisesRegex(RuntimeError, "dirty"):
            inspect_local_checkout(self.repo)

    def test_synced_folder_and_nonrepository_rejected(self):
        linked = Path(self.tmp.name) / "My Drive" / "checkout"
        with self.assertRaisesRegex(RuntimeError, "private local disk"):
            inspect_local_checkout(linked)
        with self.assertRaisesRegex(RuntimeError, "Git checkout verification failed"):
            inspect_local_checkout(Path(self.tmp.name))


if __name__ == "__main__":
    unittest.main()
