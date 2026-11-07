import unittest
from pathlib import Path

class OfflineWorkflowPermissions(unittest.TestCase):
 def test_read_only_checkout_without_persistent_credentials(self):
  path=Path(__file__).resolve().parents[1]/".github/workflows/microgen-offline-tests.yml"
  text=path.read_text()
  self.assertIn("permissions:\n  contents: read",text)
  self.assertIn("persist-credentials: false",text)
  self.assertNotIn("contents: write",text)
 def test_windows_only_platform_and_budget(self):
  text=(Path(__file__).resolve().parents[1]/".github/workflows/microgen-offline-tests.yml").read_text()
  self.assertIn('os: [windows-latest]',text)
  self.assertNotIn('ubuntu-latest',text)
  self.assertNotIn('linux-',text)
  self.assertIn('python: ["3.11", "3.12"]',text)
  self.assertIn("timeout-minutes: 15",text)
  self.assertIn("python -m unittest discover -s tests -v",text)
