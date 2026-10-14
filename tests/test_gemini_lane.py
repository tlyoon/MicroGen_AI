import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gemini_lane


class FakeBillingError(Exception):
    code = 402

    def __str__(self):
        return "Your prepayment credits are depleted. Please manage your project and billing."


class GeminiLaneTests(unittest.TestCase):
    def test_billing_error_trips_shared_circuit_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = {"n": 0}

            def operation():
                calls["n"] += 1
                raise FakeBillingError()

            env = {
                "MICROGEN_GEMINI_LANE_DIR": tmp,
                "MICROGEN_GEMINI_BILLING_RECHECK_SECONDS": "3600",
                "MICROGEN_GEMINI_MAX_RETRIES": "6",
            }
            with patch.dict(os.environ, env, clear=False):
                with self.assertRaises(gemini_lane.GeminiBillingError):
                    gemini_lane.call_with_retry(operation, label="test billing")
                self.assertEqual(calls["n"], 1)
                self.assertTrue((Path(tmp) / "circuit_breaker.json").is_file())

                with self.assertRaises(gemini_lane.GeminiCircuitOpen):
                    gemini_lane.call_with_retry(lambda: "should not run")
                self.assertEqual(calls["n"], 1)

    def test_402_is_not_transient(self):
        exc = FakeBillingError()
        self.assertTrue(gemini_lane.is_billing_gemini_error(exc))
        self.assertFalse(gemini_lane.is_transient_gemini_error(exc))

    def test_timeout_is_transient(self):
        self.assertTrue(gemini_lane.is_transient_gemini_error(TimeoutError("request timed out")))

    def test_windows_network_abort_is_retryable(self):
        # Observed in the Yoga6 8.6 end-to-end run (httpx.ReadError / 10053).
        class ReadError(Exception):
            pass
        self.assertTrue(gemini_lane.is_transient_gemini_error(
            ReadError("[Errno 10053] An established connection was aborted by "
                      "the software in your host machine")))
        self.assertTrue(gemini_lane.is_transient_gemini_error(
            ConnectionResetError("Connection reset by peer")))


if __name__ == "__main__":
    unittest.main()
