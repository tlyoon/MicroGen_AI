# ============================================================
# gen_problem_sets_api_v6.py
# API-based drop-in replacement for gen_problem_sets_selenium_v5.py
# Mirrors the same flow, logging, output naming, and compile/retry logic
# ============================================================

from __future__ import annotations
import os, re, sys, time, glob, json, textwrap, math, random
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Tuple

# Console UTF-8 on Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from PyPDF2 import PdfReader
from dotenv import load_dotenv

# API libs
import google.generativeai as genai
from openai import OpenAI

# Local LaTeX fixer/runner (your existing module)
import fix_latex as fl


# ------------------- Logging -------------------
def log(msg, level="INFO"):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


# ------------------- Config --------------------
@dataclass
class CFG:
    root: Path = Path.cwd()
    wait_compile: int = 300
    # API retry
    max_api_attempts: int = 3
    api_backoff_base: float = 1.6
    api_backoff_jitter: float = 0.25

CFG = CFG()


# ------------------- Model init ----------------
# Follows your v3 pattern (env + model_choice)
# You can flip these defaults if you want.
model_name = "gemini-2.5-pro"; model_choice = "gemini"
# model_name = "gpt-4o"; model_choice = "openai"
# model_name = "o4-mini"; model_choice = "openai"
# model_name = "deepseek-reasoner"; model_choice = "deepseek"

# Load .env (walk up like v3, then fall back to CWD)
try:
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
except NameError:
    env_path = Path(os.getcwd()).parent.parent.parent / ".env"
if not env_path.is_file():
    env_path = ".env"
# also allow an immediate .env in current dir
env_path = Path(os.getcwd()) / ".env" if Path(".env").is_file() else env_path
load_dotenv(dotenv_path=env_path)

api_key_gemini = os.getenv("GEMINI_API_KEY")
api_key_oai    = os.getenv("OPENAI_API_KEY")
api_key_dsk    = os.getenv("DEEPSEEK_API_KEY")

client = None
gem_model = None

if model_choice == "gemini":
    if not api_key_gemini:
        print("❌ No GEMINI_API_KEY found in environment."); sys.exit(1)
    genai.configure(api_key=api_key_gemini)
    gem_model = genai.GenerativeModel(model_name)
elif model_choice == "openai":
    if not api_key_oai:
        print("❌ No OPENAI_API_KEY found in environment."); sys.exit(1)
    client = OpenAI(api_key=api_key_oai)
elif model_choice == "deepseek":
    if not api_key_dsk:
        print("❌ No DEEPSEEK_API_KEY found in environment."); sys.exit(1)
    client = OpenAI(api_key=api_key_dsk, base_url="https://api.deepseek.com")
else:
    print(f"❌ Unknown model_choice: {model_choice}"); sys.exit(1)

print(f"model_choice: {model_choice}; model_name: {model_name}\n")


# ============================================================
# Helpers copied/adapted from the Selenium version
# (kept identical logic for marker, section parsing, sanitization)
# ============================================================

# ---------- LaTeX/Unicode Sanitization ----------
import unicodedata, logging

def _strip_invisible(s: str) -> str:
    invis = [
        "\u200b", "\u200c", "\u200d", "\ufeff",  # ZWSP, ZWNJ, ZWJ, BOM
        "\u2028", "\u2029"                       # line/para separators
    ]
    for ch in invis:
        s = s.replace(ch, "")
    return "".join(ch for ch in s if (ord(ch) >= 32 or ch in "\n\t"))

_LATEX_REPLACEMENTS = {
    "\u00a0": " ", "\u2009": " ", "\u202f": " ",
    "“": "``", "”": "''", "„": "``", "«": "``", "»": "''",
    "‘": "`",  "’": "'", "′": "'", "″": "''",
    "–": "--", "—": "---", "−": "-",
    "…": r"\ldots{}", "•": r"\textbullet{}", "·": r"\textperiodcentered{}",
    "©": r"\textcopyright{}", "®": r"\textregistered{}", "✓": r"\checkmark{}",
    "⅓": r"$\tfrac{1}{3}$", "½": r"$\tfrac{1}{2}$", "¼": r"$\tfrac{1}{4}$", "¾": r"$\tfrac{3}{4}$",
}

_MATH_MAP = {
    "×": r"$\times$", "÷": r"$\div$", "±": r"$\pm$",
    "≤": r"$\le$", "≥": r"$\ge$", "≠": r"$\ne$", "≈": r"$\approx$",
    "∝": r"$\propto$", "∞": r"$\infty$", "√": r"$\sqrt{}$",
    "∘": r"$\circ$", "∣": r"$\mid$", "∥": r"$\parallel$", "⟂": r"$\perp$",
    "∙": r"$\cdot$", "·": r"$\cdot$", "°": r"$^\circ$",
    "Ω": r"$\Omega$", "µ": r"$\mu$", "∇": r"$\nabla$", "∂": r"$\partial$",
    "∫": r"$\int$", "∮": r"$\oint$", "∏": r"$\prod$", "∐": r"$\coprod$",
    "∧": r"$\wedge$", "∨": r"$\vee$", "¬": r"$\neg$",
    "⊂": r"$\subset$", "⊃": r"$\supset$", "⊆": r"$\subseteq$", "⊇": r"$\supseteq$",
    "⊄": r"$\nsubseteq$", "⊅": r"$\nsupseteq$", "∈": r"$\in$", "∉": r"$\notin$",
    "∩": r"$\cap$", "∪": r"$\cup$", "∴": r"$\therefore$", "∵": r"$\because$",
    "\u2011": "-", "∑": r"$\sum$", "→": r"$\to$", "←": r"$\leftarrow$", "↔": r"$\leftrightarrow$",
    "α": r"$\alpha$", "β": r"$\beta$", "γ": r"$\gamma$", "δ": r"$\delta$",
    "ε": r"$\epsilon$", "θ": r"$\theta$", "λ": r"$\lambda$", "μ": r"$\mu$",
    "π": r"$\pi$", "σ": r"$\sigma$", "φ": r"$\phi$", "ω": r"$\omega$", "Ω": r"$\Omega$",
}

def sanitize_for_latex(s: str, log_prefix="[SANITIZE]") -> str:
    if not isinstance(s, str):
        return s
    orig = s
    s = unicodedata.normalize("NFKC", s)
    s = _strip_invisible(s)
    for k, v in _LATEX_REPLACEMENTS.items():
        s = s.replace(k, v)
    for k, v in _MATH_MAP.items():
        s = s.replace(k, v)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    non_ascii = sorted({ch for ch in s if ord(ch) > 127})
    if non_ascii:
        preview = "".join(non_ascii[:20])
        logging.warning(f"{log_prefix} Non-ASCII remain after sanitize: {repr(preview)}")
    s = s.replace("ﬁ", "fi").replace("ﬂ", "fl")
    s = re.sub(r"[ \t]{2,}", " ", s)
    if s != orig:
        logging.info(f"{log_prefix} Applied LaTeX sanitization ({len(orig)} -> {len(s)}).")
    return s


# ---------- Section regex & slicing (same logic) ----------
def compile_section_regex(marker: str) -> re.Pattern:
    em = re.escape(marker)
    pat = rf"""
        ^\s*
        (?:(?i:{em}))
        (?:\s*[:.\-–—]?\s*)
        (?P<id>
            (?:\d{{1,3}}(?:[.\-–—]\d{{1,3}}){{0,3}})
          | (?:[IVXLCDM]{{1,8}}(?:[.\-–—]\d{{1,3}})?)
          | (?:[A-Z](?:[.\-–—]\d{{1,3}})?)
        )
        \b
        (?:\s*[:\-–—]?\s+(?P<title>.+))?
        $
    """
    return re.compile(pat, re.IGNORECASE | re.MULTILINE | re.VERBOSE)

def parse_sections_with_spans(text: str, section_re: re.Pattern) -> list[tuple[str, str, int, int]]:
    matches = list(section_re.finditer(text))
    out: list[tuple[str, str, int, int]] = []
    for i, m in enumerate(matches):
        sid = (m.group("id") if "id" in m.groupdict() else None) or ""
        title = (m.group("title") if "title" in m.groupdict() else None) or ""
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((sid.strip(), title.strip(), start, end))
    return out

def normalize_question_numbers(text: str) -> str:
    return re.sub(r"\n\s*(\d+)[\.)]\s*", r"\n\1. ", text)


# ============================================================
# LLM calls (API) with retry/backoff
# ============================================================

def _api_backoff_sleep(attempt: int):
    base = CFG.api_backoff_base ** attempt
    jitter = 1.0 + (random.random() - 0.5) * 2 * CFG.api_backoff_jitter
    time.sleep(max(0.75, base * jitter))

def llm_query(prompt: str) -> str:
    """
    Generic API call wrapper for Gemini/OpenAI/DeepSeek with small retry/backoff.
    Returns plain text (no tool calls).
    """
    last_err = None
    for attempt in range(1, CFG.max_api_attempts + 1):
        try:
            if model_choice == "gemini":
                resp = gem_model.generate_content(prompt)
                return (resp.text or "").strip()
            else:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}]
                )
                return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            last_err = e
            log(f"API call failed (attempt {attempt}/{CFG.max_api_attempts}): {e}", "WARN")
            if attempt < CFG.max_api_attempts:
                _api_backoff_sleep(attempt)
    raise RuntimeError(f"API failed after {CFG.max_api_attempts} attempts: {last_err}")


# ============================================================
# Marker detection logic (UI-free, but equivalent outcomes)
# ============================================================

_ALLOWED_MARKER = re.compile(r"^[A-Za-z§][A-Za-z§.\-]{0,24}$")

def count_section_hits(marker: str, pdf_text: str) -> int:
    try:
        rx = compile_section_regex(marker)
        return sum(1 for _ in rx.finditer(pdf_text))
    except re.error:
        return 0

def extract_marker_candidates_from_text(text: str) -> list[str]:
    if not text:
        return []
    out, seen = [], set()

    # 1) A single token on a line
    for m in re.finditer(r'(?m)^\s*["\'`]*([A-Za-z§][A-Za-z§.\-]{0,24})["\'`]*\s*$', text):
        tok = m.group(1)
        if _ALLOWED_MARKER.match(tok) and tok not in seen:
            seen.add(tok); out.append(tok)

    # 2) marker/keyword/identifier/heading: TOKEN
    for m in re.finditer(r'(?i)(?:marker|keyword|identifier|heading)\s*[:\-–—]\s*([A-Za-z§][A-Za-z§.\-]{0,24})', text):
        tok = m.group(1)
        if _ALLOWED_MARKER.match(tok) and tok not in seen:
            seen.add(tok); out.append(tok)

    # 3) Whitelist matches in running text
    whitelist = ["SECTION","Section","CHAPTER","Chapter","PART","Part","APPENDIX","Appendix",
                 "Unit","UNIT","Module","MODULE","Topic","TOPIC","Sec.","Ch.","Pt.","§","SectIon"]
    wl_pat = r'(?<![A-Za-z§.\-])(' + "|".join([re.escape(w) for w in whitelist]) + r')(?![A-Za-z§.\-])'
    for m in re.finditer(wl_pat, text):
        tok = m.group(1)
        if _ALLOWED_MARKER.match(tok) and tok not in seen:
            seen.add(tok); out.append(tok)
    return out

def choose_best_marker_from_text(text: str, pdf_text: str, min_hits: int = 1) -> Optional[str]:
    cands = extract_marker_candidates_from_text(text)
    if not cands:
        return None
    best, best_hits = None, -1
    for tok in cands:
        hits = count_section_hits(tok, pdf_text)
        if hits > best_hits:
            best, best_hits = tok, hits
    return best if best and best_hits >= min_hits else None

def determine_marker_via_pdf_api(pdf_text: str) -> str:
    """
    Ask the LLM (with the same instruction semantics as the UI version) to yield a single-token marker.
    Then extract/validate candidates against the PDF text and choose the best-scoring token.
    """
    base_prompt = (
        "You are given the *text* of a textbook PDF. "
        "Identify the single keyword/identifier that consistently appears at the very start of section headers "
        "for problem-set sections. The keyword must be ONE token composed only of letters plus optional '.', '-' or '§', "
        "and it must be immediately followed (on the same line) by a section id such as a number (e.g., '29.1', '12-3'), "
        "a Roman numeral (e.g., 'III'), or a letter id (e.g., 'A.1').\n\n"
        "Return ONLY that keyword (preserve its case). If none is found, return 'None'.\n\n"
        "Text excerpt:\n"
    )
    # Send a chunk (LLMs don't need the whole thing to identify the token)
    excerpt = pdf_text[:5000]
    raw = llm_query(base_prompt + excerpt)
    log(f"LLM raw marker reply (first 100): {raw[:100]!r}")

    chosen = choose_best_marker_from_text(raw, pdf_text, min_hits=1)
    if chosen and count_section_hits(chosen, pdf_text) >= 1:
        return chosen

    # Whitelist rescue path
    whitelist = ["SECTION","Section","CHAPTER","Chapter","PART","Part","APPENDIX","Appendix",
                 "Unit","UNIT","Module","MODULE","Topic","TOPIC","Sec.","Ch.","Pt.","§"]
    wl_prompt = (
        "Based only on the text shown, reply with the ONE token that most commonly starts problem-set section headers.\n"
        "Choose ONLY from this list and reply with exactly the token:\n"
        f"{', '.join(whitelist)}\n"
        "Return just the token, or 'None' if none fit.\n\n"
        "Text excerpt:\n"
    )
    raw2 = llm_query(wl_prompt + excerpt)
    log(f"LLM whitelist marker reply (first 100): {raw2[:100]!r}")
    chosen2 = choose_best_marker_from_text(raw2, pdf_text, min_hits=1)
    if chosen2 and chosen2 in whitelist and count_section_hits(chosen2, pdf_text) >= 1:
        return chosen2

    log("Could not capture a valid marker from API; falling back to 'SECTION'.", "WARN")
    return "SECTION"


# ============================================================
# Core generation
# ============================================================

def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    text = ""
    for page in reader.pages:
        try:
            text += (page.extract_text() or "") + "\n"
        except Exception:
            pass
    return text

def generate_problemset_once(section_id: str,
                             display_title: str,
                             section_content: str,
                             base_prompt_text: str) -> str:
    """
    One API pass that mirrors:
      - filled prompt file (with placeholders)
      - attached section_content.txt
      - concise instruction to output ONLY LaTeX
    Here we embed both the filled prompt and the content inline to the LLM.
    """
    # We simulate the filled file content (what v5 uploaded as tmp_prompt)
    filled_prompt = (
        base_prompt_text
            .replace("{section_id}", section_id)
            .replace("{section_title}", display_title)
            .replace("{section_content}", "(Use only the content from the attached file: section_content.txt)")
    )

    # Compose the same concise instruction semantics used in v5
    # (We include the "tmp prompt" content and the "section_content.txt" content inline.)
    instr = (
        "Please read the 'prompt file' content below and execute the instructions EXACTLY as written. "
        "Use ONLY the 'section_content.txt' content provided below as input. "
        "Your output must be a single LaTeX article .tex document that compiles with pdflatex, "
        "with no markdown/code fences or commentary. Respond ONLY with the LaTeX source.\n\n"
        "=== prompt file (gen_problems_script__filled.txt) ===\n"
        + filled_prompt +
        "\n\n=== section_content.txt ===\n" +
        section_content
    )

    # Call LLM
    latex_code = llm_query(instr)
    return (latex_code or "").strip()

def write_and_compile(section_id: str, marker: str, latex_code: str, out_dir: Path) -> bool:
    """
    Save LaTeX to {MARKER}_{id}_problemset.tex, compile via fix_latex, check PDF, and cleanup.
    Returns True if compiled, else False.
    """
    safe_id = re.sub(r'[^A-Za-z0-9\-]+', '-', section_id)
    out_tex = out_dir / f"{marker.upper()}_{safe_id}_problemset.tex"
    out_tex.write_text(sanitize_for_latex(latex_code), encoding="utf-8")

    print(f"Now to compile {out_tex.name}")
    fl.fix_latex(out_tex.name)
    pdfname = out_tex.with_suffix(".pdf").name
    ok = os.path.isfile(pdfname)
    print(f"{out_tex.name} successfully compiled?", ok)
    if ok:
        print(f"{out_tex.name} is successfully compiled")
        try:
            os.remove(f"cleaned_{out_tex.name}")
            print(f"cleaned_{out_tex.name} is removed")
        except Exception:
            pass
    else:
        print(f"{out_tex.name} is NOT successfully compiled. To retry")
    return ok


# ============================================================
# MAIN
# ============================================================

##  main():
script_dir = Path(__file__).resolve().parent
out_dir = script_dir
out_dir.mkdir(parents=True, exist_ok=True)

#pdf_path = script_dir / "source.pdf"
pdf_path = script_dir / "problems.pdf"
if not pdf_path.is_file():
    log(f"Source PDF not found: {pdf_path}", "ERR"); 
    #return

# Your base prompt file (same names as v5)
prompt_file_a = script_dir / "generate_problems_script.txt"
prompt_file_b = script_dir / "gen_problems_script.txt"
base_prompt_path = prompt_file_a if prompt_file_a.is_file() else prompt_file_b
if not base_prompt_path.is_file():
    log(f"Prompt file not found (looked for '{prompt_file_a.name}' or '{prompt_file_b.name}').", "ERR"); #return
base_prompt_text = base_prompt_path.read_text(encoding="utf-8")

# 1) Read PDF to text (for validation/slicing)
log(f"Reading PDF: {pdf_path}")
pdf_text_raw = extract_text_from_pdf(pdf_path)
log(f"Total extracted text length: {len(pdf_text_raw)}")

# Optional normalization like v5 pre-processing
normalized_text = normalize_question_numbers(pdf_text_raw)

# 2) Determine marker (API replacement of the UI capture)
marker = determine_marker_via_pdf_api(pdf_text_raw)
log(f"Using open-class marker (from PDF): {marker!r}")

SECTION_RE = compile_section_regex(marker)
sections_spans = parse_sections_with_spans(pdf_text_raw, SECTION_RE)
log(f"Found {len(sections_spans)} section headers via marker={marker!r}.")

if not sections_spans and marker.lower() != "section":
    log("No sections found with chosen marker — retrying with 'SECTION' fallback.", "WARN")
    SECTION_RE = compile_section_regex("SECTION")
    sections_spans = parse_sections_with_spans(pdf_text_raw, SECTION_RE)
    log(f"Fallback found {len(sections_spans)} sections with 'SECTION'.")

if not sections_spans:
    log("No sections detected — aborting generation.", "ERR")
    #return

# 3) For each section: build per-section prompt + content; generate LaTeX; compile; retry once if needed
try:
    for (section_id, section_title, start_idx, end_idx) in sections_spans:
        display_title = section_title if section_title else f"{marker.title()} {section_id}"
        log(f"Processing {marker.upper()} {section_id} - {display_title}")

        section_content = normalized_text[start_idx:end_idx].strip()

        # First pass
        latex_code = generate_problemset_once(
            section_id=section_id,
            display_title=display_title,
            section_content=sanitize_for_latex(section_content),
            base_prompt_text=sanitize_for_latex(base_prompt_text),
        )

        complete = (latex_code and r"\documentclass" in latex_code and r"\end{document}" in latex_code)
        if not complete:
            log(f"Response for {marker.upper()} {section_id} did not look like a complete LaTeX document; will still attempt compile.", "WARN")

        ok = write_and_compile(section_id, marker, latex_code, out_dir)
        if not ok:
            # Retry once (mirrors your v5 “submit again” branch)
            latex_code2 = generate_problemset_once(
                section_id=section_id,
                display_title=display_title,
                section_content=sanitize_for_latex(section_content),
                base_prompt_text=sanitize_for_latex(base_prompt_text),
            )
            complete2 = (latex_code2 and r"\documentclass" in latex_code2 and r"\end{document}" in latex_code2)
            if not complete2:
                log(f"Second response for {marker.upper()} {section_id} still not a complete LaTeX document.", "WARN")
            ok2 = write_and_compile(section_id, marker, latex_code2, out_dir)
            if not ok2:
                log(f"{marker.upper()} {section_id}: compilation failed after retry.", "WARN")

        log(f"Wrote/checked outputs for {marker.upper()} {section_id}. To sleep for 5 seconds")
        time.sleep(5)

    log("All sections processed.")
finally:
    pass  # (no Chrome cleanup needed)

# -------- Post-run cleanup: clean LaTeX on originals only (same pattern as v5) --------
tex_targets = [
    f for f in glob.glob("*problemset.tex")
    if not (f.startswith("cleaned_") or f.startswith("defective_") or f.startswith("sanitized_") or f.startswith("script_orig_"))
]
for tex in tex_targets:
    try:
        log(f"Cleaning LaTeX: {tex}")
        fl.fix_latex(str(tex))
    except Exception as e:
        log(f"fix_latex failed on {tex}: {e}", "WARN")

# Remove common LaTeX aux files like the v5 tail
for pat in ('*.aux','*.log','*.out','*.toc','*.nav','*.synctex.gz'):
    for p in glob.glob(pat):
        try:
            os.remove(p)
        except Exception:
            pass


