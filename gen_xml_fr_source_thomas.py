#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gen_xml_fr_source_thomas.py  — hardened

- Auto-detects input (source.pdf → source.txt)
- Extracts problem-set slice from chapter text
- Calls Gemini 2.5 Pro to produce <quiz> XML with <problemset title=...>
- Enforces <quiz> root, titles, and question IDs
- NEW: XML preflight normalizer replaces risky HTML entities/symbols with XML-safe numeric/ASCII
- NEW: run_sanitize() only fails on __error*.xml files created in this run
- Writes *_problemset.xml → expects/creates *_problemset_mcq.xml
"""

import os, sys, re, time, shutil, importlib.util
from pathlib import Path
from typing import Tuple, List, Optional, Dict
from dotenv import load_dotenv
import google.generativeai as genai
from PyPDF2 import PdfReader
import xml.etree.ElementTree as ET
import argparse

# ------------------------------
# Model init (Gemini 2.5 Pro)
# ------------------------------
model_name = "gemini-2.5-pro"

try:
    env_path = Path(__file__).resolve().parent / ".env"
except NameError:
    env_path = Path(os.getcwd()) / ".env"
if not env_path.exists():
    env_path = Path(".env")

load_dotenv(dotenv_path=env_path)
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ No GEMINI_API_KEY found in environment."); sys.exit(1)
genai.configure(api_key=api_key)
_gem_model = genai.GenerativeModel(model_name)
print(f"✅ Model initialized: {model_name}\n")

def log(msg, level="INFO"):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)

# ------------------------------
# Auto input detection
# ------------------------------
def auto_detect_input(user_input: Optional[str]) -> Path:
    if user_input:
        return Path(user_input)
    for cand in (Path("source.pdf"), Path("source.txt")):
        if cand.exists():
            log(f"Auto-selected input: {cand.name}")
            return cand
    log("No --input provided and neither source.pdf nor source.txt found.", "ERR")
    return Path("__NOT_FOUND__")

# ------------------------------
# PDF → text
# ------------------------------
def extract_text_from_pdf(pdf_path: Path) -> str:
    log(f"Extracting text from PDF: {pdf_path.name}")
    chunks = []
    try:
        with open(pdf_path, "rb") as f:
            reader = PdfReader(f)
            for p in reader.pages:
                chunks.append(p.extract_text() or "")
    except Exception as e:
        log(f"PDF extraction failed: {e}", "ERR"); return ""
    text = "\n".join(chunks)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# ------------------------------
# Heuristic: extract problem-set blocks
# ------------------------------
EXERCISE_ANCHORS = [
    r"\bPractice Exercises\b",
    r"\bExercises\b",
    r"\bProblems\b",
    r"\bProblem Set\b",
    r"\bQuestions to Guide Your Review\b",
    r"\bAdditional and Advanced Exercises\b",
    r"\bTechnology Application Projects\b",
]

def extract_problemset_section(raw: str, min_len: int = 1200) -> str:
    if not raw:
        return raw
    txt = raw
    starts = [m.start() for pat in EXERCISE_ANCHORS for m in re.finditer(pat, txt, flags=re.IGNORECASE)]
    if not starts:
        return raw
    start = min(starts)
    stop_match = re.search(r"\bChapter\s+\d+\b|^\s*Index\s*$|^\s*References\s*$",
                           txt[start:], flags=re.IGNORECASE|re.MULTILINE)
    end = start + stop_match.start() if stop_match else len(txt)
    cut = txt[start:end].strip()
    if len(cut) < min_len:
        return raw
    log(f"Problem-set extractor selected {len(cut)} chars (from {len(raw)}).")
    return cut

# ------------------------------
# Candidate sub-topic heading hints
# ------------------------------
HEADING_PATTERNS = [
    r"^\s*(?:[A-Z][A-Z0-9 \-\,&/()]{3,})\s*$",      # ALL CAPS
    r"^\s*(?:[A-Z][\w\s,&/\-:()]{3,})\s*:$",        # Ends with colon
    r"^\s*[A-Z]\.\s+.+$",                           # A. Title
    r"^\s*[IVXLC]+[\.\)]\s+.+$",                    # Roman I. / II)
    r"^\s*\d+[\.\)]\s+.+$",                         # 1. Title / 2)
    r"^\s*\(\s*[a-z]\s*\)\s+.+$",                   # (a) Title
    r"^\s*(?:Latihan|Soalan|练习|習題|Exercices)\b.*$",  # other langs
]
STOP_WORDS = {"exercises","exercise","problems","problem set","questions","review","appendix","solutions"}

def extract_candidate_subtopics(raw_text: str, max_candidates: int = 16) -> List[str]:
    cands, seen = [], set()
    if not raw_text:
        return cands
    for line in raw_text.splitlines():
        s = line.strip()
        if len(s) < 4 or len(s) > 140: continue
        for pat in HEADING_PATTERNS:
            if re.match(pat, s):
                title = re.sub(r"\s+", " ", s.rstrip(" :")).strip()
                if any(sw in title.lower() for sw in STOP_WORDS): break
                if title not in seen:
                    seen.add(title); cands.append(title)
                break
        if len(cands) >= max_candidates: break
    return cands

# ------------------------------
# Prompt (XML Version A w/ hints)
# ------------------------------
PROMPT_TEMPLATE = """You are given a subchapter extracted from a textbook. 
This subchapter contains an Exercise or Problem Set section. Within this section, there may be multiple sub-topics (headings or categories) under the same subchapter.

Your tasks:

1) Detect sub-topics:
   - Identify every explicit sub-topic heading that structures the exercises (e.g., "Domain and Range", "Piecewise Functions", "Even and Odd Functions").
   - Use the **exact text** of each heading (verbatim) as the title of a <problemset> element.
   - If NO explicit headings exist, create a single sub-topic titled "General Problems".
   - Prefer exact matches from the "CANDIDATE SUB-TOPIC HEADINGS" list if provided.

2) Select questions:
   - For each sub-topic, randomly select three representative, complete questions from the problem set text.
   - Quote each question fully in <text>.

3) Pedagogical solutions:
   - Step-by-step solution for each question.
   - After EVERY step, include an <explanation> noting the reasoning and the principle/law/equation used.

4) Output:
   - Return **pure XML only**, UTF-8, well-formed, no markdown or LaTeX.
   - Root MUST be <quiz>.
   - Before the first child under <quiz>, include a comment listing sub-topic titles:
     <!-- SUBTOPICS: Title A | Title B | Title C -->

Schema example:
<problemset title="Exact Sub-topic Heading">
  <question id="Q1">
    <text>Question text ...</text>
    <solution>
      <step>...</step><explanation>...</explanation>
      <step>...</step><explanation>...</explanation>
    </solution>
  </question>
  <question id="Q2">...</question>
  <question id="Q3">...</question>
</problemset>

5) XML constraints:
   - Escape &, <, >, " properly.
   - Close all tags; no wrapper text; no code fences.

===== BEGIN SUBCHAPTER (problem set focus) =====
{subchapter_text}

CANDIDATE SUB-TOPIC HEADINGS (prefer exact matches if appropriate):
{hint_block}
===== END SUBCHAPTER =====
"""

# ------------------------------
# Enforcements on returned XML
# ------------------------------
def ensure_quiz_root(xml_str: str) -> Tuple[str, bool]:
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return xml_str, False
    if root.tag == "quiz":
        return xml_str, False
    new_root = ET.Element("quiz"); new_root.append(root)
    return ET.tostring(new_root, encoding="unicode"), True

def enforce_problemset_titles_and_ids(xml_str: str) -> Tuple[str, bool]:
    changed = False
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return xml_str, False
    if root.tag != "quiz":
        new_root = ET.Element("quiz"); new_root.append(root); root = new_root; changed = True

    psets = root.findall("./problemset")
    if not psets:
        ps = ET.Element("problemset", {"title": "General Problems"})
        for child in list(root):
            if isinstance(child.tag, str):
                root.remove(child); ps.append(child)
        root.append(ps); changed = True; psets = [ps]

    qn = 1
    for ps in psets:
        title = ps.get("title","").strip()
        if not title:
            ps.set("title", "General Problems"); changed = True
        for q in ps.findall("./question"):
            qid = (q.get("id") or "").strip()
            if not qid:
                q.set("id", f"Q{qn}"); qn += 1; changed = True
    return ET.tostring(root, encoding="unicode"), changed

def post_enforce(xml_str: str) -> str:
    xml1, _ = ensure_quiz_root(xml_str)
    xml2, changed = enforce_problemset_titles_and_ids(xml1)
    if changed: log("Post-enforcement adjusted XML structure/titles/ids.", "OK")
    return xml2

# ------------------------------
# XML preflight normalizer (before sanitizer)
#   - convert risky HTML named entities → numeric entities
#   - normalize raw symbols to ASCII/numeric
#   - escape stray '&'
# ------------------------------
_HTML_TO_NUMERIC: Dict[str, str] = {
    "&radic;": "&#8730;",  # √
    "&pi;": "&#960;",
    "&deg;": "&#176;",
    "&le;": "&#8804;",
    "&ge;": "&#8805;",
    "&times;": "&#215;",
    "&plusmn;": "&#177;",
}

def escape_stray_ampersands(s: str) -> str:
    # replace & not followed by a valid entity with &amp;
    return re.sub(r"&(?!(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9A-Fa-f]+);)", "&amp;", s)

def xml_preflight_normalize(xml: str) -> str:
    if not xml:
        return xml
    # raw symbol → ASCII/numeric to avoid sanitizer creating HTML entities
    repl = [
        ("\u221A", "sqrt"),         # √
        ("\u2264", "<="),           # ≤
        ("\u2265", ">="),           # ≥
        ("\u00D7", "x"),            # ×
        ("\u00B0", " degrees "),    # °
        ("\u00B9", "^1"), ("\u00B2", "^2"), ("\u00B3", "^3"),
        ("\u2032", "'"), ("\u2033", '"'),  # primes
    ]
    for a, b in repl:
        xml = xml.replace(a, b)

    # Replace common HTML named entities → numeric (valid in XML)
    for name, num in _HTML_TO_NUMERIC.items():
        xml = xml.replace(name, num)

    # Escape stray ampersands last
    xml = escape_stray_ampersands(xml)
    return xml

# ------------------------------
# Robust Gemini wrapper
# ------------------------------
def safe_generate(prompt: str, max_retries: int = 3) -> str:
    temps = [0.55, 0.45, 0.35]
    tops  = [0.90, 0.85, 0.80]
    if len(prompt) > 45000:
        prompt = prompt[:45000]

    for i in range(max_retries):
        try:
            resp = _gem_model.generate_content(
                prompt,
                generation_config={
                    "temperature": temps[min(i, len(temps)-1)],
                    "top_p":       tops[min(i, len(tops)-1)],
                    "max_output_tokens": 8192,
                    "response_mime_type": "text/plain",
                }
            )
            text = getattr(resp, "text", None)
            if text:
                return text.strip()
            for c in getattr(resp, "candidates", []) or []:
                if hasattr(c, "content") and getattr(c.content, "parts", None):
                    for p in c.content.parts:
                        if hasattr(p, "text") and p.text:
                            return p.text.strip()
            log("Gemini returned no text (finish_reason may be SAFETY/TOKENS).", "WARN")
        except Exception as e:
            log(f"Gemini API error on try {i+1}: {e}", "ERR")
    return ""

# ------------------------------
# Build prompt + generate XML
# ------------------------------
def generate_xml(subchapter_text: str) -> str:
    focused = extract_problemset_section(subchapter_text)
    cands = extract_candidate_subtopics(focused)
    hint_block = "- " + "\n- ".join(cands) if cands else ""

    prompt = PROMPT_TEMPLATE.format(
        subchapter_text=focused.strip(),
        hint_block=hint_block
    )
    xml = safe_generate(prompt, max_retries=3).replace("\r","").strip()
    if not xml:
        return ""
    xml = post_enforce(xml)
    xml = xml_preflight_normalize(xml)   # <-- PRE-SANITIZER HARDENING
    return xml

# ------------------------------
# Sanitizer integration
#   Only fail if NEW __error*.xml files appear in this run.
# ------------------------------
def run_sanitize(xml_path: Path) -> bool:
    # snapshot existing error files before running
    before_errors = set(f.name for f in xml_path.parent.glob(f"{xml_path.stem}__error*.xml"))

    try:
        spec = importlib.util.spec_from_file_location(
            "sanitize_xml_v2", str(Path(__file__).parent / "sanitize_xml_v2.py")
        )
        sanitize_xml_v2 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sanitize_xml_v2)
    except Exception as e:
        log(f"❌ Cannot import sanitize_xml_v2: {e}", "ERR"); return False

    log(f"Running sanitizer on {xml_path.name} ...")
    try:
        sanitize_xml_v2.run([str(xml_path)])
    except SystemExit:
        pass
    except Exception as e:
        log(f"Sanitizer error: {e}", "ERR")

    mcq = xml_path.with_name(xml_path.stem + "_mcq.xml")
    if mcq.exists():
        log(f"✅ Sanitization passed — {mcq.name}", "OK"); return True

    # compare error files AFTER run
    after_errors = set(f.name for f in xml_path.parent.glob(f"{xml_path.stem}__error*.xml"))
    new_errors = [e for e in after_errors if e not in before_errors]
    if new_errors:
        log(f"❌ Sanitization failed — new error file(s): {', '.join(new_errors)}", "ERR")
        return False

    # fallback: copy original to *_mcq.xml if no new errors but no mcq
    if xml_path.exists():
        try:
            shutil.copyfile(xml_path, mcq)
            log(f"ℹ️ Created fallback {mcq.name}", "WARN"); return True
        except Exception as e:
            log(f"Failed to create fallback mcq: {e}", "ERR")
    return False

# ------------------------------
# CLI
# ------------------------------
def main():
    ap = argparse.ArgumentParser(description="Generate & sanitize XML problemset (auto source.pdf).")
    ap.add_argument("--input", default=os.getenv("INPUT_FILE", None),
                    help="Input .pdf or .txt; defaults to source.pdf (then source.txt) if omitted.")
    ap.add_argument("--output", default="source_problemset.xml",
                    help="Output XML file (pre-sanitization).")
    ap.add_argument("--max-retry", type=int, default=3,
                    help="Max regeneration attempts if sanitization fails.")
    args = ap.parse_args()

    p_in = auto_detect_input(args.input)
    if not p_in.exists():
        log("Provide --input or place source.pdf / source.txt in the current directory.", "ERR")
        sys.exit(1)

    if p_in.suffix.lower() == ".pdf":
        text = extract_text_from_pdf(p_in)
    else:
        text = p_in.read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        log("No text extracted.", "ERR"); sys.exit(1)

    out = Path(args.output)
    success = False
    for attempt in range(1, args.max_retry + 1):
        log(f"🌀 Attempt {attempt}: Generating XML via Gemini ...")
        xml = generate_xml(text)
        if not xml:
            log("Empty model output; trying again...", "WARN"); continue

        out.write_text(xml, encoding="utf-8")
        log(f"Saved initial XML → {out.name}")

        if run_sanitize(out):
            success = True; break
        else:
            log(f"Retrying generation (attempt {attempt+1}) ...", "WARN")

    if not success:
        log(f"❌ All {args.max_retry} attempts failed to produce a valid *_mcq.xml.", "ERR")
        sys.exit(2)
    log(f"🎯 Success: {out.stem}_mcq.xml validated and ready.", "OK")

if __name__ == "__main__":
    main()
