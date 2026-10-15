# MicroGen_AI — safe multi-PC ownership setup and acceptance

## What is already verified
Independent-target parallel PDF→MP4 production on HP and Dell-115 passed on 15 October 2026. That is NOT the same as two computers attempting to write the SAME subchapter. Google Drive mirroring/lock files must never be treated as atomic distributed locks.

The built-in strong lease uses **Google Cloud Storage (GCS) generation preconditions**, bound to the *same campaign ID and subchapter* on every worker. With the lease-fencing patch, live stages check ownership during execution and terminate their process tree if the lease is lost, rather than waiting for the stage to finish.

## Prerequisites — not provisioned by MicroGen

1. An existing **private** Google Cloud Storage bucket owned by your authorized Google Cloud project. Use public-access prevention and uniform bucket-level access. Do not publish credentials in the repository.
2. For each local Windows worker's **main Python** environment, install `google-cloud-storage` only if absent. The dedicated Docling Conda interpreter can remain unchanged. `python -m pip install google-cloud-storage` applies only in the chosen main environment.
3. Configure Google Application Default Credentials on each worker with the least permissions required to read, create, conditionally replace, and delete objects in the designated bucket. A bucket-scoped role such as **Storage Object User** may be suitable, subject to organizational policy. Use authorized managed ADC or a secure key file stored OUTSIDE source folders and Git. If using a key file, point the account's `GOOGLE_APPLICATION_CREDENTIALS` user environment variable to its path; the variable's value is a path, never the JSON key's contents.
4. Ensure HP, Yoga6 and Dell-115 use exactly the **same** bucket and **same stable campaign ID** for the same production tree (example: `thomas-calculus-2026`). Different campaign IDs create different lock namespaces and do NOT protect the same output. Do not reuse a campaign ID across unrelated production roots.
5. Make `--work-root` PRIVATE LOCAL scratch on each worker; it must not be a Drive-synced folder. `--source-root` must point to the authorized shared course tree. Only vetted workers should have write access to that source root.
6. Do not enable a bucket lifecycle rule that deletes potentially live `microgen/v1/` leases, or otherwise modify lock objects by hand while a job is running.

## Readiness probe — no cloud access without configuration

From each worker's **main Python** environment:

```powershell
python microgen_lease_doctor.py
```

Without a bucket, it reports prerequisites and exits code 2. It does not make external requests.

## Live disposable two-PC contention test

Once an existing bucket and valid ADC are in place, choose a *one-off shared campaign name starting with* `microgen-smoke-`; use a fresh name for each run. The test only touches the disposable target `999.999` in the lock bucket, NEVER a textbook folder.

First, on HP:

```powershell
python microgen_lease_doctor.py --bucket YOUR_AUTHORIZED_BUCKET --campaign microgen-smoke-acceptance-20261015 --hold-seconds 90
```

Wait until it prints `LEASE_ACQUIRED`, then on Dell-115:

```powershell
python microgen_lease_doctor.py --bucket YOUR_AUTHORIZED_BUCKET --campaign microgen-smoke-acceptance-20261015 --expect-busy
```

Dell must print `EXPECTED_BUSY` and exit 0. After HP releases, run the same doctor on Dell without `--expect-busy`, which must acquire and release. Repeat with Yoga6. If any test fails, DO NOT start same-target production.

## Production invocation (only AFTER live lease acceptance)

With the same approved bucket and campaign ID on all participating PCs:

```powershell
python microgen_batch.py --repo YOUR_LOCAL_MICROGEN_CLONE `
  --source-root "G:\My Drive\Projects\Thomas_calculus_13ed" `
  --work-root "$env:LOCALAPPDATA\MicroGen_scratch" `
  --targets "8.4,8.5" --multi-pc `
  --lease-bucket YOUR_AUTHORIZED_BUCKET --campaign-id thomas-calculus-2026 `
  --commit VERIFIED_MAIN_SHA --stage-retries 1 --fail-fast
```

Do not point multiple workers to a shared scratch directory. Keep Gemini billing/capacity checks enabled and use the approved source-root write permissions.

## Fail-closed safety and residual limitations

- A second claimant should receive `LeaseBusy` while the first lease is valid.
- A lost lease interrupts running stages and cancels their descendants; only the current lease holder can publish a verified source-adjacent bundle. Windows stages begin suspended, are attached to a kill-on-close Job Object, then resume so early-spawned descendants cannot escape; merely calling `taskkill /T` proved unreliable on HP.
- Existing completed outputs are verified and skipped; a failed attempt is checkpointed for review.
- Network partition/delayed GCS responses can still delay discovery of lease loss; production cannot guarantee zero physical in-flight work during an outage. The conditional lease protects publication when probes resume.
- **Offline fake GCS tests do not prove two real Windows hosts can both reach the same bucket and enforce its preconditions.** Keep this gate blocked until the live test above passes.
- No academic sign-off or Moodle publication is implied by successful technical generation.
