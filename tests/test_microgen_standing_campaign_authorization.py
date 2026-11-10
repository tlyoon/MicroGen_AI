"""Regression: a finite private campaign never asks for per-stage approval.

Exercises the REAL batch main entrypoint with no model calls, and explicitly
rejects broader paid campaigns, source/code/model drift, forged receipts and
retry-budget enlargement. No credentials or copyrighted sources are used.
"""
from __future__ import annotations

from contextlib import nullcontext
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import microgen_batch as batch
import microgen_campaign_authorization as permit


class StandingBoundedCampaignTests(unittest.TestCase):
    def setUp(self):
        self.private = tempfile.TemporaryDirectory()
        self.addCleanup(self.private.cleanup)
        self.root = Path(self.private.name)
        self.repo = self.root / "candidate_repo"
        self.repo.mkdir()
        self.sources = self.root / "sources"
        self.dest = self.sources / "2" / "2.5"
        self.dest.mkdir(parents=True)
        self.source = self.dest / "source.pdf"
        self.source.write_bytes(b"%PDF-1.4\nfixture source no copyrighted content\n")
        self.work = self.root / "private_scratch"
        self.original_revision = "a" * 40
        self.opts = dict(
            repo=self.repo, source_root=self.sources, work_root=self.work,
            source_file=self.source, stop_after="acceptance",
            stage_retries=0, multipart=False,
        )

    def admit(self, authorized):
        with patch.object(permit, "_revision",
                          return_value=self.original_revision):
            return permit.authorize_or_resume(
                **self.opts, explicit_authorization=authorized)

    def test_unapproved_scope_fails_without_persisting_authorization(self):
        with self.assertRaisesRegex(
                permit.BoundedCampaignAuthorizationError,
                "NO_STANDING_PROVIDER_SCOPE"):
            self.admit(False)
        self.assertFalse((self.work / permit.RECEIPT).exists())

    def test_one_time_scope_is_durably_reused_without_reapproval(self):
        created = self.admit(True)
        self.assertEqual(created["status"], "FROZEN_ONE_TIME_PROVIDER_SCOPE")
        receipt = self.work / permit.RECEIPT
        original = receipt.read_bytes()
        accepted = self.admit(False)
        self.assertEqual(accepted["status"], "REUSED_EXACT_BOUNDED_PROVIDER_SCOPE")
        self.assertEqual(receipt.read_bytes(), original)
        record = json.loads(original)
        self.assertFalse(record["publication_authorized"])
        self.assertEqual(record["scope"]["stop_after"], "acceptance")
        self.assertEqual(record["scope"]["source_sha256"],
                         permit._sha(self.source))

    def test_revision_source_model_and_stage_drift_fail_closed(self):
        self.admit(True)
        for change in (
            {"stop_after": "video"},
            {"stop_after": "science_qa"},
            {"multipart": True},
        ):
            with self.subTest(change=change):
                with patch.object(permit, "_revision",
                                  return_value=self.original_revision):
                    with self.assertRaisesRegex(
                            permit.BoundedCampaignAuthorizationError, "scope changed"):
                        permit.authorize_or_resume(
                            **(self.opts | change),
                            explicit_authorization=False)
        with patch.object(permit, "_revision", return_value="b" * 40):
            with self.assertRaisesRegex(
                    permit.BoundedCampaignAuthorizationError, "scope changed"):
                permit.authorize_or_resume(
                    **self.opts, explicit_authorization=False)
        with patch.dict(os.environ, {"MICROGEN_FORMAL_TTS_PROVIDER": "google_cloud"}):
            with self.assertRaisesRegex(
                    permit.BoundedCampaignAuthorizationError, "scope changed"):
                self.admit(False)
        self.source.write_bytes(b"modified private source")
        with self.assertRaisesRegex(
                permit.BoundedCampaignAuthorizationError, "scope changed"):
            self.admit(False)

    def test_retry_budget_can_only_decrease(self):
        self.admit(True)
        with patch.object(permit, "_revision",
                          return_value=self.original_revision):
            with self.assertRaisesRegex(
                    permit.BoundedCampaignAuthorizationError, "Cannot increase"):
                permit.authorize_or_resume(
                    **(self.opts | {"stage_retries": 1}),
                    explicit_authorization=False)

    def test_corrupted_receipt_and_unsafe_publication_scope_rejected(self):
        self.admit(True)
        receipt = self.work / permit.RECEIPT
        receipt.write_text("{not-json", encoding="utf-8")
        with self.assertRaisesRegex(
                permit.BoundedCampaignAuthorizationError, "Corrupt"):
            self.admit(False)
        receipt.unlink()
        self.opts["stop_after"] = "published"
        with self.assertRaisesRegex(
                permit.BoundedCampaignAuthorizationError, "unpublished"):
            self.admit(True)

    def test_normal_batch_caller_auto_resumes_authorized_scope(self):
        initial_args = [
            "microgen_batch.py", "--repo", str(self.repo),
            "--source-root", str(self.sources), "--work-root", str(self.work),
            "--targets", "2.5", "--stop-after", "acceptance",
            "--stage-retries", "0", "--authorize-provider-usage",
        ]
        # Verify normal CLI goes all the way to an ordinary batch dispatch.
        # The provider and generation are mocked; this test grants no API use.
        for argv, expected in (
            (initial_args, "FROZEN_ONE_TIME_PROVIDER_SCOPE"),
            ([arg for arg in initial_args if arg != "--authorize-provider-usage"],
             "REUSED_EXACT_BOUNDED_PROVIDER_SCOPE"),
        ):
            with self.subTest(scope=expected):
                with patch.object(sys, "argv", argv), \
                     patch.object(permit, "_revision",
                                  return_value=self.original_revision), \
                     patch.object(batch, "destination_for",
                                  return_value=self.dest), \
                     patch.object(batch.quality, "require_scratch_space",
                                  return_value={"free_gb": 20, "required_gb": 8}), \
                     patch.object(batch, "resolve_docling_python",
                                  return_value=sys.executable), \
                     patch.object(batch, "preflight") as preflight, \
                     patch.object(batch, "subchapter_ownership",
                                  return_value=nullcontext(None)), \
                     patch.object(batch, "process_one") as dispatch:
                    self.assertEqual(batch.main(), 0)
                    dispatch.assert_called_once()
                    preflight.assert_called_once()
        self.assertTrue((self.work / permit.RECEIPT).is_file())

    def test_checkpointed_prior_failure_cannot_reset_attempts_next_session(self):
        self.admit(True)
        stage = self.work / "2.5"
        stage.mkdir()
        checkpoint = stage / ".microgen_checkpoint.json"
        checkpoint.write_text(json.dumps({
            "completed": {"figure_merge": "already checked"},
            "last_error": {"stage": "slides", "type": "RuntimeError",
                           "message": "Gemini provider failed; finite attempt spent"},
        }), encoding="utf-8")
        with self.assertRaisesRegex(
                permit.BoundedCampaignAuthorizationError,
                "PRIOR_STAGE_FAILURE_HOLD"):
            self.admit(False)
        # Repeating --authorize-provider-usage cannot make an exhausted
        # recorded attempt disappear, either.
        with self.assertRaisesRegex(
                permit.BoundedCampaignAuthorizationError,
                "PRIOR_STAGE_FAILURE_HOLD"):
            self.admit(True)
        checkpoint.write_text(json.dumps({
            "completed": {"slides": "verified"},
            "last_error": None,
        }), encoding="utf-8")
        self.assertEqual(
            self.admit(False)["status"],
            "REUSED_EXACT_BOUNDED_PROVIDER_SCOPE")

    def test_corrupted_previous_checkpoint_fails_closed(self):
        self.admit(True)
        stage = self.work / "2.5"
        stage.mkdir()
        (stage / ".microgen_checkpoint.json").write_text(
            "invalid", encoding="utf-8")
        with self.assertRaisesRegex(
                permit.BoundedCampaignAuthorizationError,
                "Unverifiable prior attempt"):
            self.admit(False)

    def test_unapproved_normal_batch_fails_before_stage_dispatch(self):
        argv = [
            "microgen_batch.py", "--repo", str(self.repo),
            "--source-root", str(self.sources), "--work-root", str(self.work),
            "--targets", "2.5", "--stop-after", "acceptance",
            "--stage-retries", "0",
        ]
        with patch.object(sys, "argv", argv), \
             patch.object(permit, "_revision",
                          return_value=self.original_revision), \
             patch.object(batch.quality, "require_scratch_space",
                          return_value={"free_gb": 20, "required_gb": 8}), \
             patch.object(batch, "destination_for", return_value=self.dest), \
             patch.object(batch, "preflight") as preflight, \
             patch.object(batch, "process_one") as dispatch:
            with self.assertRaisesRegex(SystemExit, "NO_STANDING_PROVIDER_SCOPE"):
                batch.main()
            preflight.assert_not_called()
            dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
