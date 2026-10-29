"""Owner 30-Oct-2026 TTS provider split: diagnostic Cloud vs formal default."""
from __future__ import annotations
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import microgen_cloud_tts_diagnostic as diag
import microgen_tts_provider_policy as policy
import text_to_speech_v25 as formal


def synthetic_wav(dest):
    with wave.open(str(dest), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\x02\x00" * 2400)


class TTSDiagnosticContractTests(unittest.TestCase):
    def test_formal_default_is_not_cloud_and_fails_before_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "not_created" / "slide1.wav"
            with patch.dict(os.environ, {"MICROGEN_FORMAL_TTS_PROVIDER": ""}), \
                 patch.object(formal, "_google_synthesize") as paid, \
                 patch.object(formal, "_load_runtime_environment") as credential:
                self.assertEqual(policy.selected_formal_provider(), "unconfigured")
                with self.assertRaises(policy.TTSProviderPolicyError):
                    formal.main()
                with self.assertRaises(policy.TTSProviderPolicyError):
                    formal.synthesize("This is a valid phrase.", target)
                paid.assert_not_called()
                credential.assert_not_called()
                self.assertFalse(target.parent.exists())

    def test_established_dotenv_formal_selector_is_read_without_secret_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            envfile = config / ".env"
            envfile.write_text(
                "MICROGEN_FORMAL_TTS_PROVIDER=google_cloud\n"
                "SOME_PRIVATE_KEY=never_echo_or_load\n",
                encoding="utf-8",
            )
            values = {"MICROVID_CONFIG_DIR": str(config)}
            self.assertEqual(policy.selected_formal_provider(values), "google_cloud")
            self.assertEqual(policy.selected_formal_provider(
                {**values, "MICROGEN_FORMAL_TTS_PROVIDER": "unconfigured"}),
                "unconfigured")
            envfile.write_text("SOME_PRIVATE_KEY=irrelevant\n", encoding="utf-8")
            self.assertEqual(policy.selected_formal_provider(values), "unconfigured")

    def test_formal_cloud_possible_only_with_explicit_selection(self):
        with patch.dict(os.environ, {"MICROGEN_FORMAL_TTS_PROVIDER": "google_cloud"}):
            self.assertEqual(policy.require_formal_provider(), "google_cloud")
        for bad in ("sapi", "auto", "microsoft", "some_random"):
            with self.subTest(value=bad), \
                 patch.dict(os.environ, {"MICROGEN_FORMAL_TTS_PROVIDER": bad}):
                with self.assertRaises(policy.TTSProviderPolicyError):
                    policy.require_formal_provider()

    def test_unapproved_or_oversize_cloud_diagnostic_is_rejected_before_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for confirm,text in ((False,"One sentence."),(True,"a"*501),(True,"")):
                with self.subTest(confirm=confirm, size=len(text)):
                    dest = root / ("diagnostic_" + str(confirm) + str(len(text)))
                    with patch.object(formal, "_google_synthesize") as paid, \
                         patch.object(formal, "_load_runtime_environment") as credential:
                        with self.assertRaises(policy.TTSProviderPolicyError):
                            diag.run_diagnostic(text,dest,confirm_chargeable=confirm)
                        paid.assert_not_called()
                        credential.assert_not_called()
                        self.assertFalse(dest.exists())

    def test_one_cloud_diagnostic_produces_isolated_nonformal_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            dest=root/"new_diagnostic_run"
            calls=[]
            def fake(spoken, output, *, max_attempts=4):
                calls.append((spoken,max_attempts))
                synthetic_wav(output)
                return "google_cloud_chirp3"
            with patch.object(formal,"_load_runtime_environment") as creds, \
                 patch.object(formal,"_google_synthesize",side_effect=fake):
                result=diag.run_diagnostic(
                    "At c. Next, check the limit.",dest,confirm_chargeable=True)
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0][1],1)
            self.assertIn("at see.",calls[0][0].lower())
            self.assertFalse(result["publication_allowed"])
            self.assertFalse(result["formal_tts_default_changed_to_cloud"])
            self.assertFalse(result["formal_tts_manifest_created"])
            self.assertTrue((dest/"diagnostic_cloud_tts_NOT_FORMAL.wav").is_file())
            self.assertTrue((dest/"diagnostic_receipt.json").is_file())
            self.assertFalse((dest/"slide1.wav").exists())
            with patch.object(formal,"_google_synthesize") as paid:
                with self.assertRaises(policy.TTSProviderPolicyError):
                    diag.run_diagnostic("A second attempt.",dest,confirm_chargeable=True)
                paid.assert_not_called()
            creds.assert_called_once()

    def test_failed_single_call_cleans_only_new_diagnostic_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            sentinel=root/"KEEP_USER_FILE.txt"
            sentinel.write_text("protected",encoding="utf8")
            dest=root/"failed_diagnostic_trial"
            with patch.object(formal,"_load_runtime_environment"), \
                 patch.object(formal,"_google_synthesize",
                              side_effect=RuntimeError("fake cloud outage")) as paid:
                with self.assertRaisesRegex(RuntimeError,"fake cloud outage"):
                    diag.run_diagnostic("Short test.",dest,confirm_chargeable=True)
                paid.assert_called_once()
            self.assertFalse(dest.exists())
            self.assertEqual(sentinel.read_text(encoding="utf8"),"protected")

    def test_non_diagnostic_directory_rejected_without_cloud_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            for folder in ("lecture_output","slide1.wav","production_voice"):
                with self.subTest(folder=folder):
                    dest=Path(tmp)/folder
                    with patch.object(formal,"_google_synthesize") as paid:
                        with self.assertRaises(policy.TTSProviderPolicyError):
                            diag.run_diagnostic("One test.",dest,confirm_chargeable=True)
                        paid.assert_not_called()

    def test_formal_cloud_retry_policy_is_separate_from_one_call_diagnostic(self):
        self.assertEqual(formal._google_synthesize.__kwdefaults__["max_attempts"],4)
        self.assertEqual(policy.diagnostic_request_allowed(
            character_count=500,confirmation=True,output_is_new=True),True)
        with self.assertRaises(policy.TTSProviderPolicyError):
            policy.diagnostic_request_allowed(
                character_count=501,confirmation=True,output_is_new=True)


if __name__=="__main__":
    unittest.main()
