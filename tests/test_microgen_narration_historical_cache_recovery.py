"""Historical provider responses are source/permit bound and rehashed locally."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from microgen_narration_batch import generate_batched
from microgen_narration_cache_recovery import reuse_verified_narration_batches


def create_stage(root: Path, campaign: str, source: bytes, revision: str) -> Path:
    stage = root / campaign / "2.7"
    stage.mkdir(parents=True)
    (stage / "source.pdf").write_bytes(source)
    sha = hashlib.sha256(source).hexdigest()
    grant = {
        "publication_authorized": False,
        "scope": {
            "host": "hp", "stop_after": "acceptance",
            "code_revision": revision, "source_sha256": sha,
        },
    }
    (stage.parent / ".microgen_bounded_provider_authorization.json").write_text(
        json.dumps(grant), encoding="utf8")
    (stage / ".microgen_checkpoint.json").write_text(
        json.dumps({"package_commit": revision}), encoding="utf8")
    return stage


class NarrationHistoryCacheRecovery(unittest.TestCase):
    slides = [{"id": "S1", "title": "Source topic", "text": "A source fact"}]
    source_blocks = [{"page": 1, "content": "Source topic and verified units"}]

    def generate(self, slides, source):
        return {s["id"]: {"narration": s["title"], "tts_text": s["title"]}
                for s in slides}

    def test_reuses_exact_completed_request_without_provider(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = create_stage(root, "old", b"original verified PDF", "a" * 64)
            new = create_stage(root, "new", b"original verified PDF", "b" * 64)
            existing = old / ".microgen_narration_batches"
            generate_batched(self.slides, self.source_blocks, self.generate,
                             cache_dir=existing, model="flash")
            receipt = reuse_verified_narration_batches(
                new, checkpoint_root=root, require_hp=False)
            self.assertEqual(receipt["copied"], 1)
            result = generate_batched(
                self.slides, self.source_blocks,
                lambda *_: self.fail("must not repurchase accepted response"),
                cache_dir=new / ".microgen_narration_batches", model="flash")
            self.assertEqual(result["S1"]["narration"], "Source topic")

    def test_different_composed_prompt_is_never_trusted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = create_stage(root, "old", b"PDF", "a" * 64)
            new = create_stage(root, "new", b"PDF", "b" * 64)
            generate_batched(self.slides, self.source_blocks, self.generate,
                             cache_dir=old / ".microgen_narration_batches",
                             model="flash", prompt_hash="OLD")
            reuse_verified_narration_batches(
                new, checkpoint_root=root, require_hp=False)
            calls = []
            def generator(slides, source):
                calls.append(1)
                return self.generate(slides, source)
            generate_batched(self.slides, self.source_blocks, generator,
                             cache_dir=new / ".microgen_narration_batches",
                             model="flash", prompt_hash="NEW")
            self.assertEqual(len(calls), 1)

    def test_source_mismatch_and_unverified_authorization_abstain(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = create_stage(root, "old", b"ORIGINAL", "a" * 64)
            new = create_stage(root, "new", b"DIFFERENT", "b" * 64)
            generate_batched(self.slides, self.source_blocks, self.generate,
                             cache_dir=old / ".microgen_narration_batches",
                             model="flash")
            receipt = reuse_verified_narration_batches(
                new, checkpoint_root=root, require_hp=False)
            self.assertEqual(receipt["copied"], 0)
            (new.parent / ".microgen_bounded_provider_authorization.json").unlink()
            self.assertEqual(reuse_verified_narration_batches(
                new, checkpoint_root=root, require_hp=False)["status"],
                "CURRENT_CAMPAIGN_UNVERIFIED")

    def test_normal_batch_invokes_recovery_before_provider_invocation(self):
        import inspect
        from microgen_batch import process_one
        body = inspect.getsource(process_one)
        self.assertIn('stage_name == "narration"', body)
        self.assertIn('reuse_verified_narration_batches(stage)', body)
        self.assertLess(body.index('reuse_verified_narration_batches(stage)'),
                        body.index('run_subprocess('))
        self.assertIn('bounded_provider_scope_verified', body)

    def test_corrupt_historical_payload_never_copied(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = create_stage(root, "old", b"PDF", "a" * 64)
            new = create_stage(root, "new", b"PDF", "b" * 64)
            cache = old / ".microgen_narration_batches"
            cache.mkdir()
            (cache / "batch_0000.json").write_text(
                json.dumps({"key": "broken", "narration": {"S1": {}}}),
                encoding="utf8")
            receipt = reuse_verified_narration_batches(
                new, checkpoint_root=root, require_hp=False)
            self.assertEqual(receipt["copied"], 0)
            self.assertFalse((new / ".microgen_narration_batches" / "batch_0000.json").exists())


if __name__ == "__main__":
    unittest.main()
