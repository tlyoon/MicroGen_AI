# Safe three-PC deployment and recovery for MicroGen_AI

## Purpose

Keep the runnable Git checkout on an ordinary local Windows disk on every PC. A synced Google Drive or OneDrive folder remains suitable for the **authorized source PDFs and final artifacts**, but is not a reliable place to perform concurrent Git checkout replacement, heavy PDF compilation, FFmpeg scratch work, or per-PC virtual environments.

This distinction was confirmed during the 2026-10-14 Yoga6 recovery: `git pull --ff-only` against a Drive-backed repository failed while replacing two tracked Python files. One machine reported access-denied/EPERM; all three Drive replicas showed a mixed state with an outdated Git HEAD and newly written untracked files. **Never attempt `git reset --hard` or delete these protected files as a first fix.**

## One-time setup on each PC

Use PowerShell (with Git and Python already installed):

```powershell
$code = Join-Path $env:LOCALAPPDATA 'MicroGen_AI'
if (Test-Path $code) { throw "Choose an empty local clone directory; preserve existing files" }
git clone https://github.com/tlyoon/MicroGen_AI $code
git -C $code rev-parse HEAD
git -C $code status --short --branch
```

For an existing **healthy local clone** with no uncommitted changes:

```powershell
git -C $code fetch origin main
git -C $code merge --ff-only origin/main
```

Do not automatically switch a running worker to a new commit. Pause/start workers at a clean stage boundary; retain their checkpoints and verify dependency hashes.

Use source root `G:\My Drive\Projects\Thomas_calculus_13ed` **only if it exists and is writable by that Windows user**. Select a separate local scratch root such as `$env:LOCALAPPDATA\MicroGenJobs`. Never use the code directory as the source root or the Drive source directory as scratch. Production outputs follow MicroGen's source-adjacent publication rules.

## Offline preflight before a campaign

```powershell
Set-Location $code
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m unittest discover -s tests -p 'test_microgen_*.py' -q
python microgen_doctor.py --source-root 'G:\My Drive\Projects\Thomas_calculus_13ed' --work-root $env:LOCALAPPDATA --json
```

Check Python, PDF/figure imports, FFmpeg, pdflatex, Docling, source access, and at least 8 GB local disk capacity. `microgen_doctor.py` does **not** prove Gemini service availability or academic quality. Passing unit tests does not constitute a live end-to-end production test.

For machines requiring a separate installed Docling interpreter, set the MicroGen-only user environment setting **after validating imports**:

```powershell
$doclingPython = Join-Path $env:LOCALAPPDATA 'MicroGen_Docling\Scripts\python.exe'
& $doclingPython -c 'from docling.document_converter import DocumentConverter; import pdf2image,PIL'
if ($LASTEXITCODE -ne 0) { throw 'Docling interpreter is unusable' }
[Environment]::SetEnvironmentVariable('MICROGEN_DOCLING_PY', $doclingPython, 'User')
$env:MICROGEN_DOCLING_PY = $doclingPython
```

**Existing Anaconda/Miniconda installations:** before installing anything, examine
`$env:LOCALAPPDATA\\miniconda3\\envs`,
`$env:LOCALAPPDATA\\miniforge3\\envs` and user-home Conda locations.
For example, an existing environment may be at
`$env:LOCALAPPDATA\\miniconda3\\envs\\docling_win\\python.exe`.
Test that interpreter directly with the import command above. Cold imports of
`DocumentConverter` can take longer than 40 seconds on some Windows PCs,
so the bounded discovery/import deadline is 90 seconds. If a long-lived remote
agent does not inherit a pre-existing Windows user `MICROGEN_DOCLING_PY`
setting, MicroGen now reads the persisted HKCU setting without modifying it.
An explicit `--docling-py` or current process setting still takes priority.
Do not assume that an old, stale agent environment means Docling is missing.

The Docling environment is deliberately independent of other applications. Do not modify global pip index settings or pre-existing Conda environments solely to repair MicroGen. In a temporary terminal session, pip can avoid a nonfunctional extra package index by overriding `PIP_EXTRA_INDEX_URL`; do not persist a machine-wide change without review.

## Synchronization rules

- Pin the **same tested Git commit** on HP, Yoga6 and Dell-115; verify the full SHA, not merely that the branch is called `main`.
- Use only the approved source root; do not copy credentials, `.env`, browser profiles, or caches between machines. Authentication remains per-user outside Git.
- The synchronized Drive tree is **not an atomic distributed lock**. Use the **Drive-native immutable, SHA-pinned, single-owner assignment manifest** documented in `DRIVE_NATIVE_MULTIPC_ASSIGNMENTS.md`. GCS is not required or selected; do not automatically reassign an interrupted worker.
- Preserve original textbook `source.pdf`, valid WAVs, existing MP4s, review receipts, and prior completed outputs. Run new tests in isolated source-authorized copies.
- A generated MP4, a technically passing PDF, or an offline test suite **does not grant academic review or student-publication approval**.

## Recovering a broken Drive-backed checkout

1. Stop using the compromised checkout for execution. Do not remove unreadable/locked files.
2. Record `git status`, the current HEAD, remote HEAD, and failing filename/permission error.
3. Create a **new local clone** from the verified GitHub main and independently run regressions.
4. Continue execution only from that verified clone. Leave the Drive checkout for a later, explicit backup-and-repair procedure.
5. If later cleaning the old Drive folder, first check for unrelated files, locally changed code, cloud sync state, and any workers referencing the folder. Never run a blanket reset in the presence of unresolved permissions.

The 2026-10-14 recovery used the merged commit `c16876ef8a83290dea977f340b87dbdcbbd46531`; local clones on all three PCs passed 82 offline tests each. This is a historical acceptance marker, **not** a permanent version pin for future runs.


## 16 October 2026: verified local checkouts after Drive cache divergence

On HP and Dell-115, `G:\My Drive\Projects\MicroGen_AI\microgen_quality.py`
had a stale 28,078-byte version removing figure-legibility, narration-title and
canonical figure-hash checks. Yoga 6 saw the intact 35,920-byte version.
Local backups and textual patches were preserved on each affected PC under
`%LOCALAPPDATA%\MicroGen_AI_Backups\20261016_1708_sync`.
Never merge the damaged file just because its Drive timestamp is newer.

In-place Git operations against the Drive checkout failed with `File exists`,
`Access is denied`, or permission errors. A fresh versioned Drive clone
appeared **partially hydrated** on other PCs, with no committed main branch.
Visibility of a folder is not proof of checkout integrity. Do not launch
production code from it.

Clean independent local-disk clones at
`%LOCALAPPDATA%\MicroGen_AI_Verified_20261016` were checked out at
`2142b8c221b76a58de28c5ebabc49f4836685677` and passed 138 automated
tests on EACH of HP, Dell-115, and Yoga 6 (one skipped). These are the
verified runnable code copies, not the partially synchronized Drive checkout.

Production multi-PC entry now checks that `--repo` points to a local clean
Git repository, refuses recognized synchronized-drive paths, and verifies
an optional full `--commit` pin. If `--commit` is not supplied it records
the verified full Git HEAD. `--check-assignments` remains a read-only
diagnostic and does not require this production gate.

Example before launching a new campaign (the source root remains on Drive):

```powershell
$code = Join-Path $env:LOCALAPPDATA 'MicroGen_AI_Verified_20261016'
git -C $code rev-parse HEAD
git -C $code status --porcelain
python (Join-Path $code 'microgen_batch.py') --help
```

The valid published Thomas 8.4, 8.5, 8.6 media and existing lecturer reviewer
bundles were **not overwritten** during this recovery. The academic-review
assumption given by the user is separate from technical tests and does not
authorize inventing a signed review file.
