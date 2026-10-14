"""Fail-closed review of panel compositions before final publication."""
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from microgen_figure_composition import FigureCollector, FigureCompositionError, validate_figure_receipt
import microgen_quality as quality


class FigureReviewGateTests(unittest.TestCase):
    def prepare(self, root, count=2):
        root = Path(root)
        folder = root / "figures"
        c = FigureCollector(folder)
        for n in range(count):
            source = root / f"input{n}.png"
            Image.new("RGB", (15, 16), ("blue" if n else "red")).save(source)
            c.add(folder / "Figure 7.2.png", source, source_page="page_2")
        data = c.finalize()
        return folder, data["figures"][0]

    def approve(self, folder, figure):
        evidence = {
            "schema_version": 1, "reviewer": "Human reviewer",
            "review_note": "Checked original panels, order, all labels and captions",
            "figures": [{
                "destination": figure["destination"],
                "output_sha256": figure["output_sha256"],
                "source_page": figure["source_page"],
                "panel_count": figure["panel_count"],
                "approved": True
            }]
        }
        path = folder / "figure_review_approval.json"
        path.write_text(json.dumps(evidence), encoding="utf-8")
        return path

    def test_composite_requires_explicit_hash_bound_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, entry = self.prepare(temp)
            self.assertTrue(entry["review_required"])
            validate_figure_receipt(folder)  # Mapping checkpoint remains usable.
            with self.assertRaisesRegex(FigureCompositionError, "human review"):
                validate_figure_receipt(folder, require_review=True)
            self.approve(folder, entry)
            self.assertEqual(len(validate_figure_receipt(folder, require_review=True)["figures"]), 1)
            # An old approval cannot certify a regenerated different composition.
            data = json.loads((folder / "figure_review_approval.json").read_text())
            data["figures"][0]["output_sha256"] = "0" * 64
            (folder / "figure_review_approval.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(FigureCompositionError, "mismatched"):
                validate_figure_receipt(folder, require_review=True)

    def test_unapproved_or_duplicate_review_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, entry = self.prepare(temp)
            approval = self.approve(folder, entry)
            record = json.loads(approval.read_text())
            record["figures"][0]["approved"] = False
            approval.write_text(json.dumps(record))
            with self.assertRaisesRegex(FigureCompositionError, "unapproved"):
                validate_figure_receipt(folder, require_review=True)
            record["figures"][0]["approved"] = True
            record["figures"].append(dict(record["figures"][0]))
            approval.write_text(json.dumps(record))
            with self.assertRaisesRegex(FigureCompositionError, "Duplicate"):
                validate_figure_receipt(folder, require_review=True)

    def test_single_panel_does_not_require_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, entry = self.prepare(temp, count=1)
            self.assertFalse(entry["review_required"])
            validate_figure_receipt(folder, require_review=True)

    def test_final_manifest_checks_approval_but_mapping_does_not(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            folder, entry = self.prepare(stage)
            for filename in ("source.pdf", "slides.tex"):
                (folder / filename).write_bytes(b"valid-only-under-mock")
            with (mock.patch.object(quality, "check_slide_pdf", return_value={"pages": 1, "sha256": "pdf"}),
                  mock.patch.object(quality, "check_graphics", return_value=[]),
                  mock.patch.object(quality, "check_narration", return_value={"script_sha256": "s", "sidecar_sha256": "c"}),
                  mock.patch.object(quality, "check_wavs", return_value={"sha256": ["w"], "total_seconds": 3}),
                  mock.patch.object(quality, "check_video", return_value={"sha256": "v", "seconds": 3})):
                with self.assertRaisesRegex(FigureCompositionError, "human review"):
                    quality.manifest_for(folder)
                self.approve(folder, entry)
                result = quality.manifest_for(folder)
                self.assertIn("figure_review_approval_sha256", result)

    def test_publication_retains_approval_and_rejects_tampering(self):
        from unittest import mock
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage, entry = self.prepare(root)
            self.approve(stage, entry)
            for name in ("source.pdf", "slides.pdf", "slides.tex", "script.txt",
                         "script_tts.json", "slides.mp4", "slide1.wav"):
                (stage / name).write_bytes(b"test-artifact:" + name.encode("utf-8"))
            dest = root / "publication"
            dest.mkdir()
            shutil.copy2(stage / "source.pdf", dest / "source.pdf")
            digest = quality.sha256
            with (mock.patch.object(quality, "check_slide_pdf", return_value={
                      "pages": 1, "sha256": digest(stage / "slides.pdf")}),
                  mock.patch.object(quality, "check_graphics", return_value=[]),
                  mock.patch.object(quality, "check_narration", return_value={
                      "script_sha256": digest(stage / "script.txt"),
                      "sidecar_sha256": digest(stage / "script_tts.json")}),
                  mock.patch.object(quality, "check_wavs", return_value={
                      "sha256": [digest(stage / "slide1.wav")], "total_seconds": 3.0}),
                  mock.patch.object(quality, "check_video", return_value={
                      "sha256": digest(stage / "slides.mp4"), "seconds": 3.0})):
                manifest = quality.manifest_for(stage)
                quality.publish_bundle(stage, dest, manifest=manifest)
            self.assertTrue(quality.published_manifest_valid(dest))
            approval = dest / "figure_review_approval.json"
            data = json.loads(approval.read_text())
            data["review_note"] = "Changed review record"
            approval.write_text(json.dumps(data), encoding="utf-8")
            self.assertFalse(quality.published_manifest_valid(dest))


if __name__ == "__main__":
    unittest.main()
