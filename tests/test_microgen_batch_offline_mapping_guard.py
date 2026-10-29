"""Fail-closed no-provider batch flag regression."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import microgen_batch


class OfflineMappingBatchPolicyTests(unittest.TestCase):
    def command(self, tmp, *, stop="figure_merge", extra=()):
        return [
            "microgen_batch.py", "--repo", str(tmp),
            "--source-root", str(tmp), "--work-root", str(tmp / "scratch"),
            "--targets", "1.1", "--offline-figure-mapping", "--stop-after", stop,
            *extra,
        ]

    def run_rejected(self, stop="figure_merge", extra=()):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(sys, "argv", self.command(root, stop=stop, extra=extra)):
                with patch.object(microgen_batch.quality, "require_scratch_space",
                                  return_value={"free_gb": 30, "required_gb": 8}):
                    with patch.object(microgen_batch, "inspect_local_checkout",
                                      return_value="0" * 40):
                        with patch.object(microgen_batch, "preflight") as preflight:
                            with patch.object(microgen_batch, "process_one") as production:
                                with self.assertRaises(SystemExit):
                                    microgen_batch.main()
                                preflight.assert_not_called()
                                production.assert_not_called()

    def test_offline_mapping_refuses_slides_even_with_no_provider_flag(self):
        for step in ("slides", "narration", "tts", "video"):
            with self.subTest(stop_after=step):
                self.run_rejected(stop=step)

    def test_offline_mapping_refuses_provider_authorization_even_if_requested(self):
        self.run_rejected(extra=["--authorize-provider-usage"])

    def test_offline_mapping_refuses_multi_pc_and_extraction_conflict(self):
        self.run_rejected(extra=["--multi-pc"])
        self.run_rejected(extra=["--figure-extraction-only"])

    def test_offline_mapping_requires_explicit_bounded_mode(self):
        self.run_rejected(stop="figure_extraction")

    def test_offline_mapping_refuses_multipart_mode(self):
        self.run_rejected(extra=["--multipart"])

    def test_offline_map_parser_accepts_only_explicit_flag(self):
        args = microgen_batch.build_parser().parse_args([
            "--source-root", "original", "--work-root", "scratch",
            "--targets", "1.1", "--offline-figure-mapping",
            "--stop-after", "figure_merge"
        ])
        self.assertTrue(args.offline_figure_mapping)
        self.assertFalse(args.authorize_provider_usage)


if __name__ == "__main__":
    unittest.main()
