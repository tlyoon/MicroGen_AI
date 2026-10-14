"""Source-crop coverage audit: unnumbered exercise images are not silently invisible."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image
from microgen_figure_composition import FigureCollector, audit_unmapped_source_crops
import microgen_quality as quality


class UnmappedSourceCropAuditTests(unittest.TestCase):
    def prepare(self, root):
        root = Path(root)
        crops = root / "crops" / "page_6"
        crops.mkdir(parents=True, exist_ok=True)
        for i in (1, 2):
            Image.new("RGB", (20, 18), "red" if i == 1 else "blue").save(crops / f"fig_{i}.png")
        collector = FigureCollector(root)
        collector.add(root / "Figure 8.6.png", crops / "fig_1.png", source_page="page_6")
        receipt = collector.finalize()
        return root, receipt

    def test_unmapped_exercise_crop_is_reported_with_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, receipt = self.prepare(temp)
            missing = audit_unmapped_source_crops(folder, receipt=receipt)
            self.assertEqual(len(missing), 1)
            self.assertEqual(missing[0]["source_page"], "page_6")
            self.assertEqual(missing[0]["filename"], "fig_2.png")
            self.assertTrue(missing[0]["review_required"])
            self.assertEqual(missing[0]["source_sha256"], quality.sha256(folder / "crops/page_6/fig_2.png"))

    def test_no_missing_crops_without_extraction_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, receipt = self.prepare(temp)
            (folder / "crops/page_6/fig_2.png").unlink()
            self.assertEqual(audit_unmapped_source_crops(folder, receipt=receipt), [])
            self.assertEqual(audit_unmapped_source_crops(folder / "unknown", receipt={"figures": []}), [])

    def test_final_verified_manifest_carries_unmapped_figure_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, receipt = self.prepare(temp)
            for name in ("source.pdf", "slides.tex", "slides.pdf", "script.txt",
                         "script_tts.json", "slides.mp4", "slide1.wav"):
                (folder / name).write_bytes(("dummy-" + name).encode())
            h = quality.sha256
            with (mock.patch.object(quality, "check_slide_pdf", return_value={"pages": 1, "sha256": h(folder / "slides.pdf")}),
                  mock.patch.object(quality, "check_graphics", return_value=[]),
                  mock.patch.object(quality, "check_narration", return_value={"script_sha256": h(folder / "script.txt"), "sidecar_sha256": h(folder / "script_tts.json")}),
                  mock.patch.object(quality, "check_wavs", return_value={"sha256": [h(folder / "slide1.wav")], "total_seconds": 1.0}),
                  mock.patch.object(quality, "check_video", return_value={"sha256": h(folder / "slides.mp4"), "seconds": 1.0})):
                info = quality.manifest_for(folder)
                self.assertTrue(info["scientific_review_pending"])
                self.assertEqual(info["unmapped_source_crops"][0]["filename"], "fig_2.png")
                dest = folder / "output"
                dest.mkdir()
                (dest / "source.pdf").write_bytes((folder / "source.pdf").read_bytes())
                quality.publish_bundle(folder, dest, manifest=info)
            self.assertTrue(quality.published_manifest_valid(dest))
            published = json.loads((dest / ".microgen_verified_completion.json").read_text())
            self.assertTrue(published["scientific_review_pending"])
            self.assertEqual(published["unmapped_source_crops"][0]["filename"], "fig_2.png")


if __name__ == "__main__":
    unittest.main()
