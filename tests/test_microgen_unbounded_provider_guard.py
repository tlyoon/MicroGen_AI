"""Offline regression: default full batch cannot silently call billed APIs."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import microgen_batch as batch

class ProviderGuardTests(unittest.TestCase):
    def test_unbounded_without_authorization_rejects_before_fs_or_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            work=root/"must_not_be_created"
            args=["batch.py","--source-root",str(root),
                  "--work-root",str(work),"--targets","1.1"]
            with patch.object(sys,"argv",args):
                with patch.object(batch,"preflight") as preflight:
                    with patch.object(batch,"process_one") as process:
                        with self.assertRaises(SystemExit) as err:
                            batch.main()
                        self.assertIn("--authorize-provider-usage",str(err.exception))
                        self.assertFalse(work.exists())
                        preflight.assert_not_called()
                        process.assert_not_called()

    def test_unbounded_multi_pc_also_requires_authorization_pre_checkout(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            argv=["batch.py","--source-root",str(root),
                  "--work-root",str(root/"work"),"--targets","1.1",
                  "--multi-pc"]
            with patch.object(sys,"argv",argv):
                with patch.object(batch,"inspect_local_checkout") as inspect:
                    with self.assertRaises(SystemExit):
                        batch.main()
                    inspect.assert_not_called()

    def test_explicit_no_provider_modes_remain_supported_by_parser(self):
        cases=[
            ["--figure-extraction-only"],
            ["--offline-figure-mapping","--stop-after","figure_merge"],
            ["--stop-after","figure_extraction"],
        ]
        for extra in cases:
            with self.subTest(args=extra):
                opts=batch.build_parser().parse_args([
                    "--source-root","source","--work-root","scratch",
                    "--targets","1.1",*extra])
                self.assertFalse(opts.authorize_provider_usage)

    def test_explicit_permission_does_not_claim_zero_cost(self):
        opts=batch.build_parser().parse_args([
            "--source-root","source","--work-root","scratch",
            "--targets","1.1","--authorize-provider-usage"])
        self.assertTrue(opts.authorize_provider_usage)

if __name__=="__main__":
    unittest.main()
