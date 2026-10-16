"""Fail-closed scene/timing/audio integrity rules for legacy MP4 repair."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import microgen_legacy_video_repair as repair


class LegacyVideoRepairTests(unittest.TestCase):
    def test_expected_scene_count_and_order(self):
        s = "pts_time:6.2\npts_time:39.4\n"
        self.assertEqual(repair.parse_scene_pts(s, 3, 80), [6.2, 39.4])
        with self.assertRaisesRegex(repair.VideoRepairError, "Expected 3"):
            repair.parse_scene_pts(s, 4, 80)
        with self.assertRaisesRegex(repair.VideoRepairError, "timings invalid"):
            repair.parse_scene_pts("pts_time:6\npts_time:5", 3, 80)

    def test_midpoints_fail_if_scene_too_short_to_inspect(self):
        self.assertEqual(repair.scene_midpoints([6, 39], 81), [3, 22, 60])
        with self.assertRaisesRegex(repair.VideoRepairError, "stable interior"):
            repair.scene_midpoints([0.5, 2], 80)

    def test_audio_packet_hash_uses_codec_copy(self):
        with mock.patch.object(repair, "run_ffmpeg") as ff:
            ff.return_value.stdout = "SHA256=" + "c" * 64 + "\n"
            self.assertEqual(repair.audio_stream_hash(Path("unused.mp4")), "c" * 64)
            self.assertEqual(ff.call_args.args[0][-7:],
                             ["-c:a", "copy", "-f", "hash", "-hash", "SHA256", "-"])
            ff.return_value.stdout = "not a hash"
            with self.assertRaisesRegex(repair.VideoRepairError, "Cannot hash"):
                repair.audio_stream_hash(Path("unused.mp4"))

    def test_refuses_overwrite_and_synced_output_without_loading_media(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_dir = root / "source"
            input_dir.mkdir()
            for item in ("slides.pdf", "slides.mp4"):
                (input_dir / item).write_bytes(b"x")
            pdf = root / "corrected.pdf"
            pdf.write_bytes(b"x")
            with self.assertRaisesRegex(repair.VideoRepairError, "already exists"):
                repair.ensure_safe_paths(input_dir, pdf, input_dir)
            with self.assertRaisesRegex(repair.VideoRepairError, "independent"):
                repair.ensure_safe_paths(input_dir, pdf, input_dir / "child")
            with self.assertRaisesRegex(repair.VideoRepairError, "local disk"):
                repair.ensure_safe_paths(input_dir, pdf, root.parent / "My Drive" / "output")

    def test_scene_count_guard_cannot_be_bypassed_with_wav_guesses(self):
        with mock.patch.object(repair, "run_ffmpeg") as ff:
            ff.return_value.stderr = "pts_time:5\npts_time:20"
            with self.assertRaisesRegex(repair.VideoRepairError, "Expected 17"):
                repair.detect_scene_times(Path("any.mp4"), 18, 80)

    def test_stale_wavs_and_narration_sidecar_are_rejected(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "script_tts.json").write_text(json.dumps({
                "slides": [{"slide": i} for i in range(1, 3)]
            }))
            (folder / "slide1.wav").write_bytes(b"old-wave")
            (folder / "slide2.wav").write_bytes(b"old-wave")
            self.assertEqual(
                repair.inspect_source_timing_provenance(folder, 2)["wav_files_present"], 2
            )
            (folder / "slide3.wav").write_bytes(b"stale-wave")
            with self.assertRaisesRegex(repair.VideoRepairError, "Stale WAV set"):
                repair.inspect_source_timing_provenance(folder, 2)
            (folder / "slide3.wav").unlink()
            with self.assertRaisesRegex(repair.VideoRepairError, "sidecar slide indices"):
                repair.inspect_source_timing_provenance(folder, 3)

    def test_regenerated_video_timing_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(repair, "media_duration", return_value=40.0), \
                 mock.patch.object(repair, "detect_scene_times", return_value=[6.5, 20.0]):
                with self.assertRaisesRegex(repair.VideoRepairError, "transitions shifted"):
                    repair.verify_candidate_synchronization(
                        Path("dummy.mp4"), Path("dummy.pdf"), [6.0, 20.0], 40.0, root
                    )
            with mock.patch.object(repair, "media_duration", return_value=40.0), \
                 mock.patch.object(repair, "detect_scene_times", return_value=[6.0, 20.0]), \
                 mock.patch.object(repair, "validate_visual_mapping", return_value=[{"scene": 1}]):
                data = repair.verify_candidate_synchronization(
                    Path("dummy.mp4"), Path("dummy.pdf"), [6.0, 20.0], 40.0, root
                )
                self.assertEqual(data["scene_timing_error_seconds"], [0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
