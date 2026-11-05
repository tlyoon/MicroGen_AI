"""Regression for automatic offline deployment recovery and preflight safety."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import microgen_runtime_preflight as runtime


class RuntimePreflightTests(unittest.TestCase):
    def test_sdk_probe_requires_retry_http_constructor_before_paid_work(self):
        code=runtime.SDK_PROBE_CODE
        compile(code,"<SDK_PROBE_CODE>","exec")
        self.assertIn("HttpRetryOptions",code)
        self.assertIn("google-genai>=2.33,<3",code)
        self.assertIn("types.HttpOptions(",code)
        self.assertNotIn("GEMINI_API_KEY",code)

    def test_find_existing_user_local_media_without_path_or_network(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/"media_tools"/"bin"
            folder.mkdir(parents=True)
            (folder/"ffprobe.exe").write_bytes(b"not-an-executable")
            (folder/"ffmpeg.exe").write_bytes(b"not-an-executable")
            with mock.patch("microgen_runtime_preflight._config_root",
                            return_value=Path(temp)), \
                 mock.patch("microgen_runtime_preflight.shutil.which",
                            return_value=None), \
                 mock.patch("microgen_runtime_preflight._validated",
                            return_value=True), \
                 mock.patch.dict(os.environ,{"PATH":"X:/localtools"},
                                 clear=False):
                os.environ.pop("MICROGEN_FFPROBE",None)
                os.environ.pop("MICROVID_FFMPEG",None)
                os.environ.pop("MICROGEN_MEDIA_BIN",None)
                state=runtime.prepare_media_tools()
                self.assertTrue(state["ffprobe_available"])
                self.assertTrue(state["ffmpeg_h264_available"])
                self.assertTrue(os.environ["PATH"].startswith(str(folder)))
                self.assertEqual(Path(os.environ["MICROVID_FFMPEG"]).name,
                                 "ffmpeg.exe")

    def test_no_ffprobe_is_fatal_before_paid_generation_no_installs(self):
        with mock.patch("microgen_runtime_preflight.find_ffprobe",
                        return_value=None), \
             mock.patch("microgen_runtime_preflight.find_h264_ffmpeg",
                        return_value="C:/valid/ffmpeg.exe"), \
             mock.patch.dict(os.environ,{"PATH":"X:/original"},
                             clear=False):
            before=os.environ["PATH"]
            with self.assertRaisesRegex(RuntimeError,"before paid generation"):
                runtime.prepare_media_tools()
            self.assertEqual(os.environ["PATH"],before)

    def test_h264_encoder_mandatory_even_with_ffprobe(self):
        with mock.patch("microgen_runtime_preflight.find_ffprobe",
                        return_value="C:/valid/ffprobe.exe"), \
             mock.patch("microgen_runtime_preflight._validated",
                        return_value=True), \
             mock.patch("microgen_runtime_preflight.find_h264_ffmpeg",
                        return_value=None):
            with self.assertRaisesRegex(RuntimeError,"libx264"):
                runtime.prepare_media_tools()

    def test_ignores_unverified_ffmpeg_without_h264(self):
        with mock.patch("microgen_runtime_preflight._ffmpeg_candidates",
                        return_value=["bad.exe","good.exe"]), \
             mock.patch("microgen_runtime_preflight._validated",
                        side_effect=[False,True]) as run:
            self.assertEqual(runtime.find_h264_ffmpeg(),"good.exe")
            self.assertEqual(run.call_count,2)

    def test_batch_fails_media_preflight_before_docling_or_provider(self):
        from microgen_batch import preflight
        with mock.patch("microgen_batch.shutil.which",return_value="pdflatex"), \
             mock.patch("microgen_batch.subprocess.run",
                        return_value=SimpleNamespace(returncode=0,stdout="sdk ok",
                                                     stderr="")) as run, \
             mock.patch("microgen_runtime_preflight.prepare_media_tools",
                        side_effect=RuntimeError("Media preflight failed before paid generation")):
            with self.assertRaisesRegex(RuntimeError,"Media preflight failed"):
                preflight("python.exe","docling.exe")
            self.assertEqual(run.call_count,1)


if __name__=="__main__":
    unittest.main()
