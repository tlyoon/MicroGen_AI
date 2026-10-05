# MicroGen_AI Educational Automation Package
# © 2025 Dr. Yoon Tiem Leong, School of Physics, Universiti Sains Malaysia.
#
# This file is part of the MicroGen_AI package.
#
# Licensed under the MIT License (see LICENSE file in the project root).
# You may not use this file except in compliance with the License.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

import subprocess, sys, os, re, shlex, time
from pathlib import Path

# Make children prefer UTF-8
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

# stdout unicode safe
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')


def _stream_run(cmd, prefix_tag=None, cwd=None):
    """
    Run a command and stream merged stdout/stderr to this process' stdout,
    forcing UTF-8 decoding so Windows cp1252 can't crash on Unicode.
    """
    # Accept either a string or a list
    if isinstance(cmd, str):
        cmd_list = shlex.split(cmd, posix=os.name != 'nt')
    else:
        cmd_list = cmd

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")

    p = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        bufsize=1,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    try:
        for line in p.stdout:
            if prefix_tag:
                sys.stdout.write(f"[{prefix_tag}] {line}")
            else:
                sys.stdout.write(line)
        p.wait()
        return p.returncode
    finally:
        try:
            if p.stdout:
                p.stdout.close()
        except Exception:
            pass


def get_latest_script(prefix: str) -> Path:
    """
    Return the latest versioned script '<prefix>_vNN.py' if present,
    otherwise '<prefix>.py'. Raises FileNotFoundError if neither exists.
    """
    cwd = Path.cwd()
    # Find versioned files like prefix_v15.py
    candidates = []
    pattern = re.compile(rf"^{re.escape(prefix)}_v(\d+)\.py$", re.IGNORECASE)
    for p in cwd.glob(f"{prefix}_v*.py"):
        m = pattern.match(p.name)
        if m:
            try:
                ver = int(m.group(1))
                candidates.append((ver, p))
            except ValueError:
                pass

    if candidates:
        candidates.sort(key=lambda t: t[0], reverse=True)
        latest = candidates[0][1]
        print(f"Latest version file to use: {latest.name}", flush=True)
        return latest

    # Fallback: non-versioned file
    fallback = cwd / f"{prefix}.py"
    if fallback.exists():
        print(f"Using non-versioned file: {fallback.name}", flush=True)
        return fallback

    raise FileNotFoundError(f"No script found for prefix '{prefix}' "
                            f"(looked for {prefix}_vNN.py or {prefix}.py)")


def prefices(prefix_list):
    """
    Accepts a list of string prefixes (e.g., ['abs_figures_merged','gen_slides']),
    resolves each to the latest script, verifies required inputs, and runs them.
    """
    # Resolve scripts
    scripts = [get_latest_script(prefix) for prefix in prefix_list]

    # Required inputs
    required_files = [p.name for p in scripts] 

    missing = [f for f in required_files if not Path(f).exists()]
    if missing:
        print("Missing required file(s):", flush=True)
        for f in missing:
            print(f" - {f}", flush=True)
        # non-zero exit so caller can stop
        sys.exit(1)
    else:
        print(f"All required files are present: {required_files}\n", flush=True)

    # Run each script sequentially
    for script_path in scripts:
        cmd = [sys.executable, "-u", str(script_path)]
        tag = script_path.stem
        print(f"Running: {' '.join(cmd)}", flush=True)
        rc = _stream_run(cmd, prefix_tag=tag)
        time.sleep(5)
        print('Slept 5 seconds')
        if rc != 0:
            print(f"{script_path} failed with return code {rc}", flush=True)
            #sys.exit(rc)

    print("All scripts completed successfully.", flush=True)


def runrunfile(items, require_source_pdf=True):
    """
    items: list[str] of prefixes (e.g., 'abs_figures_merged') or .py files.
    Resolves to latest <prefix>_vNN.py (or <prefix>.py) and runs them in order.
    """
    scripts = []
    missing_report = []

    for it in items:
        s = str(it)
        if s.lower().endswith(".py"):
            p = Path(s)
            if not p.exists():
                # Try fallback by stem (tolerate passing 'abs_figures_merged_v15.py'
                # that isn't present but a newer/older version exists)
                try:
                    p = get_latest_script(Path(s).stem)
                except FileNotFoundError:
                    missing_report.append(s)
                    continue
        else:
            # It's a prefix; resolve latest versioned script
            p = get_latest_script(s)

        scripts.append(p)

    if missing_report:
        print("Error: The following script(s) could not be resolved:")
        for f in missing_report:
            print(f" - {f}")
        sys.exit(1)

    required_files = [p.name for p in scripts]
    if require_source_pdf:
        required_files.append("source.pdf")

    missing_files = [f for f in required_files if not Path(f).exists()]
    if missing_files:
        print("Error: The following required files are missing:")
        for f in missing_files:
            print(f" - {f}")
        sys.exit(1)
    else:
        print(f"All required files are present: {required_files}\n", flush=True)

    # Run each script
    for script_path in scripts:
        cmd = [sys.executable, "-u", str(script_path)]
        tag = script_path.stem
        print(f"Running: {' '.join(cmd)}", flush=True)
        rc = _stream_run(cmd, prefix_tag=tag)
        print(f"Finished: {' '.join(cmd)}", flush=True)
        time.sleep(5)
        print('From functions.py: Have slept for 5 seconds',flush=True)
        print('')
        if rc != 0:
            print(f"{script_path} failed with return code {rc}", flush=True)
            #sys.exit(rc)            

    print("All scripts completed successfully.", flush=True)

