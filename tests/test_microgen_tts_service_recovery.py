import unittest
from microgen_tts_service_recovery import (
    run_bounded_recognition,transient_service_error,AudioRecognitionUnavailable
)

class ServiceRecoveryTests(unittest.TestCase):
    def test_503_and_429_rate_limit_can_recover_bounded(self):
        for first in ("503 Service Unavailable","429 rate limit exceeded","504 timeout"):
            with self.subTest(first=first):
                calls=[];sleeps=[]
                def api():
                    calls.append(1)
                    if len(calls)<3:raise RuntimeError(first)
                    return "Genuine words heard"
                self.assertEqual(run_bounded_recognition(api,sleeps.append),
                                 "Genuine words heard")
                self.assertEqual(len(calls),3)
                self.assertEqual(sleeps,[1,3])
    def test_auth_and_model_unavailable_fail_fast(self):
        for value in ("401 UNAUTHENTICATED","403 permission_denied",
                      "404 NOT_FOUND model not found",
                      "429 QUOTA EXCEEDED LIMIT: 0",
                      "400 INVALID_ARGUMENT"):
            calls=[]
            def api():
                calls.append(1)
                raise RuntimeError(value)
            with self.subTest(value=value),self.assertRaises(AudioRecognitionUnavailable):
                run_bounded_recognition(api,lambda _:self.fail("must not sleep"))
            self.assertEqual(len(calls),1)
    def test_unrecognized_failure_does_not_generate_spurious_retries(self):
        calls=[]
        def api():calls.append(1);raise RuntimeError("unexpected parser shape")
        with self.assertRaises(AudioRecognitionUnavailable):
            run_bounded_recognition(api,lambda _:self.fail("no sleep"))
        self.assertEqual(len(calls),1)
    def test_bounded_retry_never_forges_success(self):
        calls=[]
        def down():calls.append(1);raise RuntimeError("503 UNAVAILABLE")
        with self.assertRaises(AudioRecognitionUnavailable):
            run_bounded_recognition(down,lambda _:None)
        self.assertEqual(len(calls),3)
    def test_empty_transcript_fails_fast(self):
        with self.assertRaises(AudioRecognitionUnavailable):
            run_bounded_recognition(lambda:"",lambda _:self.fail("no sleep"))
    def test_invalid_retry_limit_rejected(self):
        for n in (0,4,-2,1.3,True):
            with self.subTest(n=n),self.assertRaises(ValueError):
                run_bounded_recognition(lambda:"fine",lambda _:None,max_attempts=n)
