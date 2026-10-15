"""In-process Gemini failover health: no redundant bad-key requests."""
import os
import tempfile
import unittest
from unittest import mock

import gemini_keys


class FakeInvalidKey(Exception):
    code = 401
    def __str__(self):
        return "API key not valid"


class FakeBillingError(Exception):
    code = 402
    def __str__(self):
        return "Your prepayment credits are depleted"


class FakeTransientError(Exception):
    code = 503
    def __str__(self):
        return "UNAVAILABLE: temporary high demand"


class GeminiCooldownTests(unittest.TestCase):
    def setUp(self):
        gemini_keys._KEY_COOLDOWN_UNTIL.clear()
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env={
            "GEMINI_API_KEY_1":"first",
            "GEMINI_API_KEY_2":"second",
            "MICROGEN_GEMINI_LANE_DIR":self.temp.name,
            "MICROGEN_GEMINI_KEY_COOLDOWN_SECONDS":"120",
        }

    def tearDown(self):
        gemini_keys._KEY_COOLDOWN_UNTIL.clear()

    def test_unavailable_key_skipped_on_next_request(self):
        calls=[]
        def operation(key):
            calls.append(key)
            if key=="first":
                raise FakeInvalidKey()
            return "ok"
        with mock.patch.dict(os.environ,self.env,clear=True):
            self.assertEqual(gemini_keys.call_with_key_failover(operation),"ok")
            self.assertEqual(gemini_keys.call_with_key_failover(operation),"ok")
        self.assertEqual(calls,["first","second","second"])
        self.assertEqual(len(gemini_keys._KEY_COOLDOWN_UNTIL),1)
        self.assertNotIn("first",str(gemini_keys._KEY_COOLDOWN_UNTIL))

    def test_expiration_restores_original_key_priority(self):
        calls=[]
        def operation(key):
            calls.append(key)
            if key=="first":
                raise FakeInvalidKey()
            return "ok"
        with mock.patch.dict(os.environ,self.env,clear=True),mock.patch(
            "gemini_keys.time.monotonic",return_value=100.0
        ) as clock:
            gemini_keys.call_with_key_failover(operation)
            clock.return_value=101.0
            gemini_keys.call_with_key_failover(operation)
            clock.return_value=221.0
            gemini_keys.call_with_key_failover(operation)
        self.assertEqual(calls,["first","second","second","first","second"])

    def test_cooldown_can_be_disabled_without_reordering(self):
        self.env["MICROGEN_GEMINI_KEY_COOLDOWN_SECONDS"]="0"
        calls=[]
        def operation(key):
            calls.append(key)
            if key=="first":
                raise FakeInvalidKey()
            return "ok"
        with mock.patch.dict(os.environ,self.env,clear=True):
            for _ in range(2):
                gemini_keys.call_with_key_failover(operation)
        self.assertEqual(calls,["first","second","first","second"])

    def test_transient_503_does_not_quarantine_key(self):
        self.env.update({
            "MICROGEN_GEMINI_BACKOFF_BASE_SECONDS":"0",
            "MICROGEN_GEMINI_BACKOFF_MAX_SECONDS":"0",
            "MICROGEN_GEMINI_TRANSIENT_RETRIES_PER_KEY":"2",
        })
        calls=[]
        def operation(key):
            calls.append(key)
            if key=="first":
                raise FakeTransientError()
            return "ok"
        with mock.patch.dict(os.environ,self.env,clear=True),mock.patch(
            "gemini_keys.time.sleep"
        ),mock.patch("gemini_keys.random.uniform",return_value=0.0):
            for _ in range(2):
                gemini_keys.call_with_key_failover(operation,max_retries=2)
        self.assertEqual(calls,["first","first","second"]*2)

    def test_billing_failure_remains_probed_for_circuit_semantics(self):
        calls=[]
        def operation(key):
            calls.append(key)
            if key=="first":
                raise FakeBillingError()
            return "ok"
        with mock.patch.dict(os.environ,self.env,clear=True):
            for _ in range(2):
                gemini_keys.call_with_key_failover(operation)
        self.assertEqual(calls,["first","second","first","second"])

    def test_all_quarantined_keys_are_reprobed(self):
        calls=[]
        def operation(key):
            calls.append(key)
            raise FakeInvalidKey()
        with mock.patch.dict(os.environ,self.env,clear=True):
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    gemini_keys.call_with_key_failover(operation)
        self.assertEqual(calls,["first","second","first","second"])

    def test_single_key_never_skipped(self):
        self.env.pop("GEMINI_API_KEY_2")
        calls=[]
        def operation(key):
            calls.append(key)
            raise FakeInvalidKey()
        with mock.patch.dict(os.environ,self.env,clear=True):
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    gemini_keys.call_with_key_failover(operation)
        self.assertEqual(calls,["first","first"])


if __name__=="__main__":
    unittest.main()
