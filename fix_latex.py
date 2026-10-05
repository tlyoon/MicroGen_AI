import os, re, sys, textwrap, subprocess, glob
from pathlib import Path
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from google import genai

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ------------------- Model init ----------------
model_name = "gemini-3.1-pro-preview"; model_choice = "gemini"

def _microvid_config_dir() -> Path:
    configured = os.environ.get("MICROVID_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Microvid"
    return Path.home() / "AppData" / "Local" / "Microvid"

env_path = _microvid_config_dir() / ".env"
if not env_path.is_file():
    raise RuntimeError(f"Shared Microvid credential file not found: {env_path}")
load_dotenv(dotenv_path=env_path, override=False)
api_key_gemini = os.getenv("GEMINI_API_KEY")
api_key_oai = os.getenv("OPENAI_API_KEY")
api_key_dsk = os.getenv("DEEPSEEK_API_KEY")
client = None
if model_choice == "gemini":
    if not api_key_gemini:
        raise RuntimeError("GEMINI_API_KEY is not configured in the shared Microvid .env")
    client = genai.Client(api_key=api_key_gemini)
elif model_choice == "openai":
    from openai import OpenAI
    client = OpenAI(api_key=api_key_oai)
elif model_choice == "deepseek":
    from openai import OpenAI
    client = OpenAI(api_key=api_key_dsk, base_url="https://api.deepseek.com")
print(f"model_choice: {model_choice}; model_name: {model_name}\n")


# =================== Config & constants ===================
BEGIN = "<<<BEGIN LATEX>>>"
END   = "<<<END LATEX>>>"

def log(msg, level="INFO"):
    import time
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


# =================== File helpers ===================
def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def _write_text(p: Path, s: str):
    p.write_text(s, encoding="utf-8")

def _backup_and_replace(original: Path, new_path: Path):
    backup = original.with_name("defective_" + original.name)
    try:
        if backup.exists():
            backup.unlink(missing_ok=True)
    except Exception:
        pass
    original.rename(backup)
    shutil_copy_ok = False
    try:
        import shutil
        shutil.copyfile(str(new_path), str(original))
        shutil_copy_ok = True
    except Exception as e:
        log(f"Copy failed: {e}", "WARN")
    if shutil_copy_ok:
        log(f"Replaced {original.name}; backup -> {backup.name}", "OK")


# =================== pdflatex ===================
def _compile_once(tex_path: Path) -> bool:
    """Run pdflatex once; returns True if compilation succeeds."""
    try:
        cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
        log(f"Running: {' '.join(cmd)} (cwd={tex_path.parent})")
        proc = subprocess.run(cmd, cwd=str(tex_path.parent),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=180)
        print(proc.stdout)
        return proc.returncode == 0
    except Exception as e:
        log(f"pdflatex error: {e}", "WARN")
        return False


# =================== Prompt handling ===================
def _locate_prompt_file(tex_path: Path) -> Path:
    """
    Search for fix_latex_prompt.txt in:
      1) env FIX_LATEX_PROMPT (if provided)
      2) same folder as the .tex
      3) alongside this script
      4) current working directory
    """
    env = os.getenv("FIX_LATEX_PROMPT")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates += [
        tex_path.parent / "fix_latex_prompt.txt",
        Path(__file__).parent / "fix_latex_prompt.txt",
        Path.cwd() / "fix_latex_prompt.txt",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("fix_latex_prompt.txt not found in expected locations.")

def _build_instruction(tex_path: Path, latex_text: str) -> str:
    """
    Load fix_latex_prompt.txt, substitute tokens, and append BEGIN/END with the LaTeX body.
    Supported tokens:
      {TEX_BASENAME}, {TEX_FILENAME}, {TEX_ABSPATH}, {BEGIN_MARKER}, {END_MARKER}
    """
    try:
        prompt_path = _locate_prompt_file(tex_path)
        raw = _read_text(prompt_path)
        subs = {
            "{TEX_BASENAME}": tex_path.name,
            "{TEX_FILENAME}": tex_path.name,
            "{TEX_ABSPATH}": str(tex_path),
            "{BEGIN_MARKER}": BEGIN,
            "{END_MARKER}": END,
        }
        for k, v in subs.items():
            raw = raw.replace(k, v)
        # If markers weren’t present in the template, still append the block
        return f"{raw.rstrip()}\n\n{BEGIN}\n{latex_text.rstrip()}\n{END}\n"
    except Exception as e:
        log(f"Prompt file load failed ({e}); using built-in minimal prompt.", "WARN")
        return textwrap.dedent(f"""\
            You are an expert LaTeX proofreader.
            - Fix this LaTeX so it compiles with pdflatex.
            - Balance all braces/environments.
            - Remove any markdown/code fences.
            - No commentary; return only LaTeX.

            {BEGIN}
            {latex_text.rstrip()}
            {END}
        """)

def _strip_md_fences(s: str) -> str:
    s = re.sub(r"^```latex\s*", "", s.strip())
    s = re.sub(r"^```\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()

def _extract_between_markers(s: str) -> str:
    m = re.search(rf"{re.escape(BEGIN)}(.*?){re.escape(END)}", s, flags=re.S)
    return (m.group(1).strip() if m else s.strip())

def _looks_like_full_latex(s: str) -> bool:
    t = s.lower()
    return "\\documentclass" in t and "\\end{document}" in t


# =================== LLM calls ===================
def _call_llm(messages_or_prompt):
    """Unified call for Gemini/OpenAI/DeepSeek; follows your v4 style."""
    if model_choice in ("openai", "deepseek"):
        # OpenAI-compatible
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": messages_or_prompt}],
            temperature=0.2,
            max_tokens=8192,
        )
        return (resp.choices[0].message.content or "").strip()
    else:
        # Gemini
        try:
            r = client.models.generate_content(model=model_name, contents=messages_or_prompt)
            return (getattr(r, "text", None) or "").strip()
        except Exception as e:
            log(f"Gemini API error: {e}", "ERR")
            return ""


# =================== Public cleaning funcs ===================
from typing import Union  
def clean_tex_file(tex_file: str | Path) -> None:
    """Lightweight local cleanup (safe transforms only)."""
    p = Path(tex_file).resolve()
    log(f"Executing clean_tex_file({p.name})")
    s = _read_text(p)
    orig = s

    # Remove stray markdown fences at file edges
    s = re.sub(r"^\s*```+.*?$", "", s, flags=re.M).strip()
    s = re.sub(r"\s*```+\s*$", "", s, flags=re.M).strip()

    # Ensure end document
    if r"\end{document}" not in s:
        s = s.rstrip() + "\n\\end{document}\n"

    cleaned = p.with_name(f"cleaned_{p.name}")
    _write_text(cleaned, s)
    log(f"Cleaned file saved as: {cleaned}")

    if s != orig:
        _backup_and_replace(p, cleaned)
    else:
        log("Original file was not defective and required no corrections.")

#def clean_tex_file2(tex_file: str, *_args, **_kwargs):
def clean_tex_file2(tex_file: Union[str, Path], *_args, **_kwargs):    
    """
    Heavy pass: send the LaTeX to the selected LLM using API keys (no Selenium).
    """
    p = Path(tex_file).resolve()
    try:
        src = _read_text(p)
        print(f"From clean_tex_file2: Loaded LaTeX file '{p.name}'. Characters:", len(src))
    except Exception as e:
        print(f"[clean_tex_file2] Error reading file '{tex_file}': {e}")
        return

    prompt = _build_instruction(p, src)
    raw = _call_llm(prompt)
    raw = _strip_md_fences(raw)

    # Prefer the region between markers; else fall back to whole response
    body = _extract_between_markers(raw) if (BEGIN in raw and END in raw) else raw
    if not _looks_like_full_latex(body):
        if _looks_like_full_latex(raw):
            body = raw
        else:
            log("API response did not look like a complete LaTeX document.", "WARN")
            return

    if body.strip() == src.strip():
        log("API response identical to input; skipping overwrite.", "INFO")
        return

    tmp = p.with_name("temp_corrected.tex")
    _write_text(tmp, body)
    _backup_and_replace(p, tmp)
    try:
        tmp.unlink(missing_ok=True)
    except Exception:
        pass


# =================== Orchestrator ===================
def fix_latex(tex_path: str):
    p = Path(tex_path).resolve()
    if not p.exists():
        log(f"File not found: {p}", "ERR"); sys.exit(1)

    # Attempt 1
    if _compile_once(p):
        log("✅ pdflatex compilation succeeded at 1st attempt", "OK"); return
    else:
        log("✅ pdflatex compilation failed at 1st attempt", "INFO")
        clean_tex_file(p)

    # Attempt 2
    if _compile_once(p):
        log("✅ pdflatex compilation succeeded at 2nd attempt", "OK"); return
    else:
        log("❌ pdflatex compilation failed at 2nd attempt.", "WARN")
        clean_tex_file2(str(p))

    # Attempt 3
    if _compile_once(p):
        log("✅ pdflatex compilation succeeded at 3rd attempt", "OK"); return
    else:
        log("✅ pdflatex compilation failed at 3rd attempt", "INFO")
        clean_tex_file(p)

    # Attempt 4
    if _compile_once(p):
        log("✅ pdflatex compilation succeeded at 4th attempt", "OK"); return
    else:
        log("✅ pdflatex compilation failed at 4th attempt", "ERR")
        # Optional: print key lines from .log
        logp = p.with_suffix(".log")
        if logp.exists():
            try:
                lines = _read_text(logp).splitlines()
                print("[latexlog] --- probable errors/warnings ---")
                for ln in lines:
                    if ln.startswith("!") or "Runaway argument" in ln or "Undefined control sequence" in ln or "Missing $" in ln:
                        print(ln)
                print("[latexlog] --- end ---")
            except Exception:
                pass


# =================== CLI ===================
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="API-only LaTeX fixer (Gemini/OpenAI/DeepSeek)")
    ap.add_argument("tex", help="Path to .tex file")
    ap.add_argument("--provider", choices=["gemini","openai","deepseek"], default=model_choice)
    ap.add_argument("--model", default=model_name)
    args = ap.parse_args()

    # Allow runtime override (optional)
    if args.provider != model_choice:
        model_choice = args.provider
    if args.model != model_name:
        model_name = args.model

    fix_latex(args.tex)
