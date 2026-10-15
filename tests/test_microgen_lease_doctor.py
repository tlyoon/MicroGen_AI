"""No-bucket lease doctor must be side-effect free."""
import unittest
from unittest import mock
import microgen_lease_doctor as doctor


class LeaseDoctorTests(unittest.TestCase):
    def test_missing_bucket_makes_no_network_calls(self):
        with mock.patch.object(doctor, "from_gcs_bucket") as acquire:
            self.assertEqual(doctor.main([]), 2)
            acquire.assert_not_called()

    def test_disposable_campaign_prefix_enforced(self):
        with self.assertRaises(SystemExit):
            doctor.main(["--bucket", "test-bucket", "--campaign", "real-production",
                         "--hold-seconds", "60"])


if __name__ == "__main__":
    unittest.main()
