"""Regression tests for the campaign's real structural acceptance failures."""
import json
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock
import microgen_quality as q


def wav(path, seconds=1.0):
    with wave.open(str(path), "wb") as obj:
        obj.setnchannels(1)
        obj.setsampwidth(2)
        obj.setframerate(8000)
        obj.writeframes(b"\x00\x00" * int(8000 * seconds))


class QualityContractTests(unittest.TestCase):
    def test_numbered_wavs_refuse_missing_middle_and_extra(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            wav(path / "slide1.wav")
            wav(path / "slide3.wav")
            with self.assertRaisesRegex(q.QualityError, "missing"):
                q.numbered_files(path, "wav", 3)
            wav(path / "slide2.wav")
            self.assertEqual(len(q.numbered_files(path, "wav", 3)), 3)
            with self.assertRaisesRegex(q.QualityError, "unexpected"):
                q.numbered_files(path, "wav", 2)

    def test_wav_validation_reads_actual_sample_duration(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            wav(path / "slide1.wav", 2.0)
            wav(path / "slide2.wav", 1.5)
            self.assertAlmostEqual(q.check_wavs(path, 2)["total_seconds"], 3.5)
            self.assertEqual(len(q.check_wavs(path, 2)["sha256"]), 2)

    def test_missing_graphic_is_a_hard_error_not_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "slides.tex").write_text(r"\includegraphics{missing_panel.png}")
            with self.assertRaisesRegex(q.QualityError, "Missing figure"):
                q.check_graphics(path / "slides.tex")
            (path / "missing_panel.png").write_bytes(b"picture")
            self.assertEqual(len(q.check_graphics(path / "slides.tex")), 1)

    def test_narration_has_exact_matching_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            text = "**Slide 1 [1 sec]:\nHello**\n\n**Slide 2 [1 sec]:\nWorld**"
            (path / "script.txt").write_text(text, encoding="utf-8")
            valid = {"slides": [
                {"slide": 1, "narration": "Hello", "tts_text": "Hello"},
                {"slide": 2, "narration": "World", "tts_text": "World"},
            ]}
            side = path / "script_tts.json"
            side.write_text(json.dumps(valid), encoding="utf-8")
            self.assertEqual(q.check_narration(path / "script.txt", side, 2)["pages"], 2)
            valid["slides"][1]["slide"] = 3
            side.write_text(json.dumps(valid), encoding="utf-8")
            with self.assertRaisesRegex(q.QualityError, "numbers"):
                q.check_narration(path / "script.txt", side, 2)

    def test_slide_counter_and_empty_page_rejected(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF absent")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "slides.pdf"
            doc = fitz.open()
            for count in (1, 2):
                page = doc.new_page()
                page.insert_text((70, 70), "Slide content")
                page.insert_text((70, 180), f"{count} / 1")
            doc.save(path)
            doc.close()
            with self.assertRaisesRegex(q.QualityError, "counters"):
                q.check_slide_pdf(path, require_footer=True)

    def test_accepted_slide_pdf_passes(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF absent")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "slides.pdf"
            doc = fitz.open()
            for count in (1, 2):
                page = doc.new_page()
                page.insert_text((70, 70), "Slide content")
                page.insert_text((70, 180), f"{count} / 2")
            doc.save(path)
            doc.close()
            self.assertEqual(q.check_slide_pdf(path, require_footer=True)["pages"], 2)

    def test_published_requires_real_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            for name in ("source.pdf", "slides.tex", "slides.pdf", "script.txt",
                         "script_tts.json", "slides.mp4"):
                (path / name).write_text(name)
            self.assertFalse(q.published_manifest_valid(path))
            keys = {
                "source_sha256": q.sha256(path / "source.pdf"),
                "slides_tex_sha256": q.sha256(path / "slides.tex"),
                "slides_pdf_sha256": q.sha256(path / "slides.pdf"),
                "script_sha256": q.sha256(path / "script.txt"),
                "sidecar_sha256": q.sha256(path / "script_tts.json"),
                "mp4_sha256": q.sha256(path / "slides.mp4"),
                "schema_version": 1,
            }
            (path / ".microgen_verified_completion.json").write_text(json.dumps(keys))
            self.assertTrue(q.published_manifest_valid(path))
            (path / "slides.mp4").write_text("tampered")
            self.assertFalse(q.published_manifest_valid(path))

    def test_crash_safe_atomic_publication_with_old_file_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            stage, dest = Path(temp) / "stage", Path(temp) / "output"
            stage.mkdir()
            dest.mkdir()
            names = ("source.pdf", "slides.tex", "slides.pdf", "script.txt",
                     "script_tts.json", "slides.mp4")
            for name in names:
                (stage / name).write_bytes(f"new:{name}".encode())
                (dest / name).write_bytes(f"old:{name}".encode())
            shutil.copyfile(stage / "source.pdf", dest / "source.pdf")
            manifest = {
                "schema_version": 1, "source_sha256": q.sha256(stage / "source.pdf"),
                "slides_tex_sha256": q.sha256(stage / "slides.tex"),
                "slides_pdf_sha256": q.sha256(stage / "slides.pdf"),
                "script_sha256": q.sha256(stage / "script.txt"),
                "sidecar_sha256": q.sha256(stage / "script_tts.json"),
                "mp4_sha256": q.sha256(stage / "slides.mp4"),
                "figure_sha256": {},
            }
            q.publish_bundle(stage, dest, manifest=manifest)
            self.assertTrue(q.published_manifest_valid(dest))
            backups = list(dest.glob("slides.mp4.before-microgen-*.bak"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), b"old:slides.mp4")

    def test_source_drift_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / "a", Path(temp) / "b"
            a.mkdir()
            b.mkdir()
            (a / "source.pdf").write_text("one")
            (b / "source.pdf").write_text("two")
            for name in ("slides.pdf", "slides.tex", "script.txt", "script_tts.json", "slides.mp4"):
                (a / name).write_text("new:" + name)
            with self.assertRaisesRegex(q.QualityError, "source PDF has changed"):
                q.publish_bundle(a, b, manifest={
                    "source_sha256": q.sha256(a / "source.pdf")
                })

    def test_video_requires_audio_and_video_and_duration(self):
        with tempfile.TemporaryDirectory() as temp:
            vid = Path(temp) / "slides.mp4"
            vid.write_bytes(b"X" * 3000)
            with mock.patch.object(q.subprocess, "run") as run:
                run.return_value = mock.Mock(stderr="Duration: 00:00:10.50\n Video: h264",stdout="")
                with self.assertRaisesRegex(q.QualityError, "both audio and video"):
                    q.check_video(vid, ffmpeg="fake_ffmpeg")
                run.return_value = mock.Mock(
                    stderr="Duration: 00:00:10.50\n Video: h264\n Audio: aac",stdout=""
                )
                with self.assertRaisesRegex(q.QualityError, "duration"):
                    q.check_video(vid, ffmpeg="fake_ffmpeg", expected_seconds=80)
                self.assertAlmostEqual(
                    q.check_video(vid, ffmpeg="fake_ffmpeg", expected_seconds=10.0)["seconds"],
                    10.5,
                )


    def test_publication_failure_rolls_back_every_changed_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            stage, dest = Path(temp) / "stage", Path(temp) / "dest"
            stage.mkdir()
            dest.mkdir()
            filenames = ("source.pdf", "slides.pdf", "slides.tex", "script.txt",
                         "script_tts.json", "slides.mp4")
            for name in filenames:
                (stage / name).write_bytes(("new:" + name).encode())
                (dest / name).write_bytes(("old:" + name).encode())
            shutil.copyfile(stage / "source.pdf", dest / "source.pdf")
            manifest = {
                "schema_version": 1,
                "source_sha256": q.sha256(stage / "source.pdf"),
                "slides_pdf_sha256": q.sha256(stage / "slides.pdf"),
                "slides_tex_sha256": q.sha256(stage / "slides.tex"),
                "script_sha256": q.sha256(stage / "script.txt"),
                "sidecar_sha256": q.sha256(stage / "script_tts.json"),
                "mp4_sha256": q.sha256(stage / "slides.mp4"),
                "figure_sha256": {},
            }
            original_replace = Path.replace
            def simulated_failure(path, target):
                if path.name.startswith("script.txt.microgen-") and path.name.endswith(".candidate"):
                    raise OSError("Drive interrupted during promotion")
                return original_replace(path, target)
            with mock.patch.object(Path, "replace", autospec=True, side_effect=simulated_failure):
                with self.assertRaisesRegex(OSError, "Drive interrupted"):
                    q.publish_bundle(stage, dest, manifest=manifest)
            for name in filenames[1:]:
                self.assertEqual((dest / name).read_bytes(), ("old:" + name).encode())
            self.assertFalse(q.published_manifest_valid(dest))

    def test_stage_fingerprint_tracks_changed_slides_or_narration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("source.pdf", "slides.pdf", "gen_script_v13.py",
                         "gen_script_prompt_v8_hybrid.md", "script_tts.json",
                         "text_to_speech_v25.py"):
                (root / name).write_text(name)
            a = q.dependency_fingerprint(root, "narration")
            b = q.dependency_fingerprint(root, "tts")
            (root / "slides.pdf").write_text("modified deck")
            self.assertNotEqual(a, q.dependency_fingerprint(root, "narration"))
            self.assertEqual(b, q.dependency_fingerprint(root, "tts"))
            (root / "script_tts.json").write_text("changed speech")
            self.assertNotEqual(b, q.dependency_fingerprint(root, "tts"))

    def test_severe_beamer_overflow_blocks_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "slides.log"
            path.write_text(
                "Overfull \\hbox (0.69pt too wide) detected at line 3\n"
                "Overfull \\vbox (28.12pt too high) has occurred\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(q.QualityError, "Severe LaTeX"):
                q.check_latex_overflow(path)
            path.write_text("Overfull \\hbox (0.69pt too wide)",encoding="utf-8")
            self.assertEqual(q.check_latex_overflow(path)["severe_count"], 0)

    def test_latex_normalization_preserves_math_and_is_idempotent(self):
        tex = ("\\begin{align*}\n\n"
               "x^2 &= 4 \\\\\n\n"
               "y &= \\frac{1}{2}\n\n"
               "\\end{align*}\n")
        out = q.normalize_latex_paragraphs(tex)
        self.assertIn("x^2 &= 4", out)
        self.assertIn("y &= \\frac{1}{2}", out)
        self.assertNotIn("\n\n", out)
        self.assertEqual(q.normalize_latex_paragraphs(out), out)

    def test_lost_lease_during_publication_rolls_back_before_receipt(self):
        from microgen_ownership import LeaseLost
        with tempfile.TemporaryDirectory() as tmp:
            stage=Path(tmp)/"stage"
            dest=Path(tmp)/"dest"
            stage.mkdir();dest.mkdir()
            for name in ("source.pdf","slides.pdf","slides.tex","script.txt",
                         "script_tts.json","slides.mp4"):
                (stage/name).write_text("new"+name)
                (dest/name).write_text("old"+name)
            (dest/"source.pdf").write_bytes((stage/"source.pdf").read_bytes())
            meta={
                "schema_version":1,
                "source_sha256":q.sha256(stage/"source.pdf"),
                "slides_pdf_sha256":q.sha256(stage/"slides.pdf"),
                "slides_tex_sha256":q.sha256(stage/"slides.tex"),
                "script_sha256":q.sha256(stage/"script.txt"),
                "sidecar_sha256":q.sha256(stage/"script_tts.json"),
                "mp4_sha256":q.sha256(stage/"slides.mp4"),
            }
            checks=[0]
            def lease_check():
                checks[0]+=1
                if checks[0]==8:
                    raise LeaseLost("lost during promotion")
            with self.assertRaisesRegex(LeaseLost,"lost during promotion"):
                q.publish_bundle(stage,dest,manifest=meta,still_owner=lease_check)
            for name in ("slides.pdf","slides.tex","script.txt","script_tts.json","slides.mp4"):
                self.assertEqual((dest/name).read_text(),"old"+name)
            self.assertFalse(q.published_manifest_valid(dest))

    def test_publication_receipt_includes_and_verifies_composite_figures(self):
        from PIL import Image
        from microgen_figure_composition import FigureCollector
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            stage=root/"stage";stage.mkdir()
            dest=root/"dest";dest.mkdir()
            source_fig=root/"page_1";source_fig.mkdir()
            panel=source_fig/"fig_1.png"
            Image.new("RGB",(16,14),"yellow").save(panel)
            c=FigureCollector(stage)
            c.add(stage/"Figure 1.7.png",panel,source_page="page_1")
            c.finalize()
            for name in ("source.pdf","slides.tex","slides.pdf","script.txt",
                         "script_tts.json","slides.mp4"):
                (stage/name).write_text("new:"+name)
            shutil.copy2(stage/"source.pdf",dest/"source.pdf")
            manifest={
                "schema_version":1,
                "source_sha256":q.sha256(stage/"source.pdf"),
                "slides_tex_sha256":q.sha256(stage/"slides.tex"),
                "slides_pdf_sha256":q.sha256(stage/"slides.pdf"),
                "script_sha256":q.sha256(stage/"script.txt"),
                "sidecar_sha256":q.sha256(stage/"script_tts.json"),
                "mp4_sha256":q.sha256(stage/"slides.mp4"),
                "figure_sha256":{"Figure 1.7.png":q.sha256(stage/"Figure 1.7.png")},
                "figure_composition_receipt_sha256":q.sha256(stage/"figure_composition_receipt.json"),
            }
            q.publish_bundle(stage,dest,manifest=manifest)
            self.assertTrue(q.published_manifest_valid(dest))
            Image.new("RGB",(20,12),"red").save(dest/"Figure 1.7.png")
            self.assertFalse(q.published_manifest_valid(dest))

if __name__ == "__main__":
    unittest.main()
