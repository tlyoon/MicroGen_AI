#!/usr/bin/env python3
"""Opt-in, disposable GCS lease contention probe for MicroGen multi-PC.

No GCS requests unless --bucket and --campaign are both supplied.
Uses an explicitly reserved test subchapter, never a real source target.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time

from microgen_ownership import LeaseBusy, LeaseLost, from_gcs_bucket


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bucket", help="Existing authorized GCS bucket (never provisioned here)")
    ap.add_argument("--campaign", help="Must begin with microgen-smoke-; identical on all participating PCs")
    ap.add_argument("--hold-seconds", type=int, default=0,
                    help="Hold the disposable lease while another PC contests it (0–120)")
    ap.add_argument("--expect-busy", action="store_true",
                    help="Succeed only if another PC already holds the exact same lease")
    args = ap.parse_args(argv)
    try:
        sdk = importlib.util.find_spec("google.cloud.storage")
    except (ModuleNotFoundError, ImportError):
        sdk = None
    print("GCS_STORAGE_SDK_PRESENT=", bool(sdk), flush=True)
    print("ADC_ENV_CONFIGURED=", bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")), flush=True)
    if not args.bucket or not args.campaign:
        print("SETUP_REQUIRED: existing GCS bucket, SDK and authorized ADC credentials; "
              "no cloud calls made.", flush=True)
        return 2
    if not args.campaign.startswith("microgen-smoke-"):
        ap.error("Disposable smoke campaigns MUST use the microgen-smoke- prefix")
    if not 0 <= args.hold_seconds <= 120:
        ap.error("--hold-seconds must be in 0..120")
    if sdk is None:
        print("BLOCKED: install google-cloud-storage into this worker's main Python environment.",
              flush=True)
        return 2
    lease = from_gcs_bucket(args.bucket, args.campaign, "999.999")
    try:
        with lease:
            if args.expect_busy:
                print("FAIL: obtained lease but expected another PC to hold it.", flush=True)
                return 1
            print("LEASE_ACQUIRED; disposable target=999.999", flush=True)
            stop = time.monotonic() + args.hold_seconds
            while time.monotonic() < stop:
                lease.assert_held()
                time.sleep(min(5.0, max(0.0, stop - time.monotonic())))
            lease.assert_held()
            print("LEASE_HELD_AND_RELEASED", flush=True)
            return 0
    except LeaseBusy:
        if args.expect_busy:
            print("EXPECTED_BUSY: independent contender correctly rejected", flush=True)
            return 0
        print("FAIL: unexpected busy lease (check for another test worker)", flush=True)
        return 1
    except LeaseLost as exc:
        print(f"FAIL: lease lost during test: {type(exc).__name__}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
