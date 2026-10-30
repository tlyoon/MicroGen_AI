"""No-network Google SDK fake verifies diagnostic retry=None and timeout."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import text_to_speech_v25 as tts


def fake_google_tree(log, *, fail=False):
    google = types.ModuleType("google")
    google.__path__ = []
    cloud = types.ModuleType("google.cloud")
    cloud.__path__ = []
    speech = types.ModuleType("google.cloud.texttospeech")

    class Params:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Client:
        def __init__(self, **kwargs):
            self.client_kwargs = kwargs
        def synthesize_speech(self, **kwargs):
            log.append(kwargs)
            if fail:
                raise RuntimeError("single diagnostic transport failure")
            return types.SimpleNamespace(audio_content=b"demo-fixture-bytes")

    speech.TextToSpeechClient = Client
    speech.SynthesisInput = Params
    speech.VoiceSelectionParams = Params
    speech.AudioConfig = Params
    speech.SsmlVoiceGender = types.SimpleNamespace(FEMALE=2)
    speech.AudioEncoding = types.SimpleNamespace(LINEAR16=1)
    google.cloud = cloud
    cloud.texttospeech = speech
    return {"google":google, "google.cloud":cloud,
            "google.cloud.texttospeech":speech}


class CloudDiagnosticSdkPolicyTests(unittest.TestCase):
    def test_single_diagnostic_disables_sdk_retries_and_sets_timeout(self):
        calls = []
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/"diagnostic.wav"
            with patch.dict(sys.modules, fake_google_tree(calls)):
                result = tts._google_synthesize("Evaluate at see.",out,max_attempts=1)
            self.assertEqual(result,"google_cloud_chirp3")
            self.assertEqual(len(calls),1)
            self.assertIsNone(calls[0]["retry"])
            self.assertEqual(calls[0]["timeout"],30.0)
            self.assertEqual(out.read_bytes(),b"demo-fixture-bytes")

    def test_formal_existing_retry_behavior_is_unchanged(self):
        calls=[]
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/"formal.wav"
            with patch.dict(sys.modules, fake_google_tree(calls)):
                tts._google_synthesize("A test.",out,max_attempts=4)
            self.assertEqual(len(calls),1)
            self.assertNotIn("retry",calls[0])
            self.assertNotIn("timeout",calls[0])

    def test_diagnostic_transport_error_makes_exactly_one_client_call(self):
        calls=[]
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/"failed.wav"
            with patch.dict(sys.modules,fake_google_tree(calls,fail=True)):
                with self.assertRaisesRegex(RuntimeError,"single diagnostic"):
                    tts._google_synthesize("Test.",out,max_attempts=1)
            self.assertEqual(len(calls),1)
            self.assertFalse(out.exists())


if __name__=="__main__":
    unittest.main()
