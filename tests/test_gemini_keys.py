import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gemini_keys
from gemini_lane import GeminiBillingError


class FakeBillingError(Exception):
    code = 402

    def __str__(self):
        return "Your prepayment credits are depleted."


class FakeTransientError(Exception):
    code = 503

    def __str__(self):
        return "UNAVAILABLE: temporary high demand"


class GeminiKeyPoolTests(unittest.TestCase):
    def test_numbered_keys_are_priority_ordered_and_deduplicated(self):
        env = {
            "GEMINI_API_KEY_2": "second",
            "GEMINI_API_KEY_1": "first",
            "GEMINI_API_KEY": "first",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(gemini_keys.get_gemini_api_keys(), ["first", "second"])

    def test_billing_failure_falls_back_before_opening_circuit(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            env = {
                "GEMINI_API_KEY_1": "first",
                "GEMINI_API_KEY_2": "second",
                "MICROGEN_GEMINI_LANE_DIR": tmp,
            }

            def operation(key):
                calls.append(key)
                if key == "first":
                    raise FakeBillingError()
                return "ok"

            with patch.dict(os.environ, env, clear=True):
                self.assertEqual(gemini_keys.call_with_key_failover(operation), "ok")
                self.assertEqual(calls, ["first", "second"])
                self.assertFalse((Path(tmp) / "circuit_breaker.json").exists())

    def test_transient_error_retries_same_key(self):
        calls = []
        env = {
            "GEMINI_API_KEY_1": "first",
            "GEMINI_API_KEY_2": "second",
            "MICROGEN_GEMINI_MAX_RETRIES": "1",
            "MICROGEN_GEMINI_BACKOFF_BASE_SECONDS": "0",
            "MICROGEN_GEMINI_BACKOFF_MAX_SECONDS": "0",
        }

        def operation(key):
            calls.append(key)
            if len(calls) == 1:
                raise FakeTransientError()
            return "ok"

        with patch.dict(os.environ, env, clear=True), patch("gemini_keys.time.sleep"), patch(
            "gemini_keys.random.uniform", return_value=0.0
        ):
            self.assertEqual(gemini_keys.call_with_key_failover(operation), "ok")
            self.assertEqual(calls, ["first", "first"])

    def test_all_billing_failures_open_shared_circuit(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "GEMINI_API_KEY_1": "first",
                "GEMINI_API_KEY_2": "second",
                "MICROGEN_GEMINI_LANE_DIR": tmp,
                "MICROGEN_GEMINI_BILLING_RECHECK_SECONDS": "60",
            }
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(GeminiBillingError):
                    gemini_keys.call_with_key_failover(lambda key: (_ for _ in ()).throw(FakeBillingError()))
                self.assertTrue((Path(tmp) / "circuit_breaker.json").is_file())


    def test_client_lifetime_is_owned_until_operation_finishes(self):
        events = []

        class FakeClient:
            def __init__(self, key):
                self.key = key
                self.closed = False
                events.append(("created", key))

            def close(self):
                self.closed = True
                events.append(("closed", self.key))

        def operation(client):
            self.assertFalse(client.closed)
            events.append(("used", client.key))
            return "ok"

        with patch.dict(os.environ, {"GEMINI_API_KEY_1": "first"}, clear=True):
            result = gemini_keys.call_with_client_failover(FakeClient, operation)

        self.assertEqual(result, "ok")
        self.assertEqual(events, [("created", "first"), ("used", "first"), ("closed", "first")])


if __name__ == "__main__":
    unittest.main()
