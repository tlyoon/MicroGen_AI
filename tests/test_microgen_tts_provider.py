"""Offline tests of the MicroGen API TTS provider contract."""
import io
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import text_to_speech_v25 as tts


def response(data, mime="audio/wav"):
    inline = SimpleNamespace(data=data, mime_type=mime)
    return SimpleNamespace(candidates=[
        SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(inline_data=inline)]))
    ])


def wav_data():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 1200)
    return buf.getvalue()


class TTSProviderTests(unittest.TestCase):
    def test_gemini_default_model_and_voice(self):
        self.assertEqual(tts.GEMINI_TTS_MODEL, "gemini-3.8-flash-lite-tts")
        self.assertEqual(tts.GEMINI_TTS_VOICE, "Kore")

    def test_gemini_request_writes_verified_wav(self):
        calls = []
        def fake_failover(factory, operation, *, label):
            client = SimpleNamespace(models=SimpleNamespace(
                generate_content=lambda **kwargs: (calls.append(kwargs), response(wav_data()))[1]
            ))
            return operation(client)
        with tempfile.TemporaryDirectory() as temp, mock.patch(
            "gemini_keys.call_with_client_failover", side_effect=fake_failover
        ):
            output = Path(temp) / "slide.wav"
            self.assertEqual(tts._gemini_synthesize("The integral is finite.", output), "gemini_flash_tts")
            with wave.open(str(output), "rb") as wav:
                self.assertGreater(wav.getnframes(), 0)
            self.assertEqual(calls[0]["model"], "gemini-3.8-flash-lite-tts")
            self.assertEqual(calls[0]["config"]["speech_config"]["voice_config"]["voice"], "Kore")

    def test_raw_l16_wraps_to_wav(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch(
            "gemini_keys.call_with_client_failover", return_value=response(
                b"\x00\x00" * 200, "audio/L16;rate=16000"
            )
        ):
            output = Path(temp) / "slide.wav"
            tts._gemini_synthesize("Example.", output)
            with wave.open(str(output), "rb") as wav:
                self.assertEqual(wav.getframerate(), 16000)
                self.assertEqual(wav.getnframes(), 200)

    def test_gemini_primary_and_cloud_opt_in_fallback(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(tts, "TTS_PROVIDER", "gemini"):
            path = Path(temp) / "slide.wav"
            with mock.patch.object(tts, "_gemini_synthesize", return_value="gemini_flash_tts") as gem, mock.patch.object(
                tts, "_google_synthesize"
            ) as cloud:
                self.assertEqual(tts.synthesize("x squared", path), "gemini_flash_tts")
                gem.assert_called_once()
                cloud.assert_not_called()
            with mock.patch.dict("os.environ", {"MICROVID_TTS_FALLBACK": "google_cloud"}), mock.patch.object(
                tts, "_gemini_synthesize", side_effect=RuntimeError("Gemini unavailable")
            ), mock.patch.object(tts, "_load_google_fallback_credentials"), mock.patch.object(
                tts, "_google_synthesize", return_value="google_cloud_chirp3"
            ) as cloud:
                self.assertEqual(tts.synthesize("test", path), "google_cloud_chirp3")
                cloud.assert_called_once()

    def test_invalid_audio_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch(
            "gemini_keys.call_with_client_failover", return_value=response(b"not-a-wave", "audio/mp3")
        ):
            with self.assertRaisesRegex(RuntimeError, "unsupported audio format"):
                tts._gemini_synthesize("Example.", Path(temp) / "bad.wav")


if __name__ == "__main__":
    unittest.main()
