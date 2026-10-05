from pathlib import Path
import sys
import re
import fix_latex
import subprocess, os
from google import genai
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')
    
######## specify model_name, from most to least expensive ######## 
##### default choice is gemini ######
#model_name = "gpt-4.1-mini"; model_choice = 'openai'
#model_name = "gpt-4o"    ; model_choice = 'openai'  
#model_name = "gpt-5-mini"    ; model_choice = 'openai'  
#model_name = "gpt-5"    ; model_choice = 'openai'  
model_name = os.environ.get("MICROVID_SLIDE_MODEL") or os.environ.get("MICROGEN_LLM_MODEL") or "gemini-3.1-pro-preview"
model_choice = 'gemini'
########  end of specify model_name, must be consistent with model_choice ######## 

# Load API credentials from the shared per-user Microvid configuration directory.
def _microvid_config_dir() -> Path:
    configured = os.environ.get("MICROVID_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Microvid"
    return Path.home() / "AppData" / "Local" / "Microvid"


config_dir = _microvid_config_dir()
env_path = config_dir / ".env"
if not env_path.is_file():
    raise RuntimeError(
        f"Shared Microvid credential file not found: {env_path}. "
        "Create %LOCALAPPDATA%\\Microvid\\.env (or set MICROVID_CONFIG_DIR)."
    )
print(f"Using shared Microvid API credentials from: {env_path}")
load_dotenv(dotenv_path=env_path, override=False)

# API key and model setup
api_key_dsk = os.getenv("DEEPSEEK_API_KEY")
api_key_oai = os.getenv("OPENAI_API_KEY")
api_key_gemini = os.getenv("GEMINI_API_KEY")

if model_choice == 'gemini':
    api_key = api_key_gemini
    print(f'model_choice: {model_choice}; model_name: {model_name}')
    if not api_key:
        print("❌ No valid API key found")
        sys.exit()
    client = genai.Client(api_key=api_key)
    
elif model_choice == 'openai':
    api_key = api_key_oai
    print(f'model_choice: {model_choice}; model_name: {model_name}')
    if not api_key:
        print("❌ No valid API key found")
        sys.exit()
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    
elif model_choice == 'deepseek':    
    api_key = api_key_dsk
    print(f'model_choice: {model_choice}; model_name: {model_name}')
    if not api_key:
        print("❌ No valid API key found")
        sys.exit()
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

print(' ')
# end of shared Microvid credential loading


def remove_missing_graphics_in_place(path: str = "slides.tex") -> None:
    """Omit any \includegraphics command whose referenced local file does not exist."""
    p = Path(path)
    if not p.is_file():
        return
    text = p.read_text(encoding="utf-8")
    rx = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
    def repl(m):
        name = m.group(1).strip()
        if Path(name).is_file():
            return m.group(0)
        print(f"[WARN] Omitting missing image reference: {name}")
        return f"% omitted missing image: {name}"
    p.write_text(rx.sub(repl, text), encoding="utf-8")


def clean_pause_in_place(path: str = "slides.tex") -> None:
    """
    Read a LaTeX Beamer file and remove any '\\pause' commands (including variants like '\\pause[...])',
    then overwrite the same file WITHOUT changing anything else (line endings preserved).

    - Removes standalone lines that are just \pause (optionally with [..]) and comments.
    - Removes inline \pause occurrences (e.g., before an \item).
    - Preserves the original file's line-ending style (\n, \r\n, or \r).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Read raw bytes to detect original newline style
    raw = p.read_bytes()
    # Determine newline sequence used
    if b"\r\n" in raw:
        newline = "\r\n"
    elif b"\r" in raw and b"\n" not in raw:
        newline = "\r"
    else:
        newline = "\n"

    # Decode (handle possible BOM gracefully)
    text = raw.decode("utf-8-sig")

    # 1) Remove standalone \pause lines (optionally with [..]) and trailing comments
    #    Example matches:
    #      \pause
    #      \pause[foo]
    #      \pause   % comment
    text = re.sub(
        r'(?m)^[ \t]*\\pause(?:\s*\[[^\]]*\])?\s*(?:%[^\n]*)?(?:\r?\n|$)',
        "",
        text
    )

    # 2) Remove any remaining inline \pause occurrences (e.g., "... \pause \item ...")
    text = re.sub(
        r'\\pause(?:\s*\[[^\]]*\])?',
        "",
        text
    )

    # Write back using the original newline style
    # (avoid collapsing newlines: only translate '\n' to the detected style)
    if newline != "\n":
        text = text.replace("\n", newline)

    p.write_text(text, encoding="utf-8")


##
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
clean_slides.py — collapse extra blank lines in a LaTeX file named 'slides.tex'

What it does (default behavior):
- Reads 'slides.tex' from the current directory.
- Treats a line as "blank-like" if it is:
    * empty or whitespace-only (including non-breaking spaces), or
    * a LaTeX comment-only line (starts with % after optional spaces).
- Collapses any run of blank-like lines to AT MOST ONE blank line.
- Does NOT introduce a leading or trailing blank line.
- Preserves the original line-ending style (LF, CRLF, or CR).
- Writes back to the same file in place.

Usage:
    python clean_slides.py
"""

'''
def normalize_latex_blank_lines_in_place(
    path: str | Path = "slides.tex",
    *,
    keep_one_blank: bool = True,
    treat_comment_only_as_blank: bool = True,
    preserve_first_comment_in_run: bool = False,
) -> None:
    """
    Collapse extra 'blank-like' lines so there is at most ONE between blocks.

    A 'blank-like' line is:
      - empty or whitespace (including non-breaking spaces U+00A0), OR
      - if treat_comment_only_as_blank is True: a LaTeX comment-only line (^\s*%.*$)

    Behavior:
      - No leading/trailing blank line will be introduced.
      - Preserves original newline style.
      - If preserve_first_comment_in_run is True and a run contains comment-only lines,
        keeps the first such comment line instead of a blank; otherwise keeps one empty line
        (if keep_one_blank=True).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    raw = p.read_bytes()

    # Detect original newline style
    if b"\r\n" in raw:
        newline = "\r\n"
    elif b"\r" in raw and b"\n" not in raw:
        newline = "\r"
    else:
        newline = "\n"

    text = raw.decode("utf-8-sig")

    # Normalize to '\n' for processing
    if newline != "\n":
        text = text.replace(newline, "\n")

    lines = text.split("\n")

    NBSP = "\u00A0"
    def is_blank_line(s: str) -> bool:
        # Consider NBSP as whitespace
        s2 = s.replace(NBSP, " ")
        return s2.strip() == ""

    def is_comment_only(s: str) -> bool:
        return re.match(r"^\s*%.*$", s) is not None

    out: list[str] = []
    seen_nonblank = False

    # Accumulate runs of blank-like lines to decide what to keep
    run_blank_like: list[str] = []

    def flush_run():
        """Emit at most one separator for the accumulated blank-like run."""
        nonlocal run_blank_like
        if not run_blank_like:
            return
        if not keep_one_blank:
            run_blank_like = []
            return
        if preserve_first_comment_in_run and treat_comment_only_as_blank:
            for line in run_blank_like:
                if is_comment_only(line):
                    out.append(line)  # keep first comment line
                    run_blank_like = []
                    return
        # Otherwise keep exactly one empty line
        out.append("")
        run_blank_like = []

    for line in lines:
        blank = is_blank_line(line)
        comment_only = treat_comment_only_as_blank and is_comment_only(line)
        is_blank_like = blank or comment_only

        if is_blank_like:
            # Skip leading blank-like lines
            if not seen_nonblank:
                continue
            run_blank_like.append(line)
            continue

        # Non blank-like line
        flush_run()
        out.append(line)
        seen_nonblank = True

    # End of file: do not emit trailing blank-like separator
    run_blank_like = []

    # Trim trailing blank-like lines if any slipped in
    while out and (is_blank_line(out[-1]) or (treat_comment_only_as_blank and is_comment_only(out[-1]))):
        out.pop()

    # Rebuild with original newline style; ensure single trailing newline
    result = "\n".join(out)
    if not result.endswith("\n"):
        result += "\n"
    if newline != "\n":
        result = result.replace("\n", newline)

    p.write_text(result, encoding="utf-8")
'''

##

def _strip_pause_commands(tex: str) -> str:
    """
    Remove all Beamer \\pause commands, whether standalone on a line
    or inline (e.g., before an \\item). Also collapse extra blank lines.
    """
    if not tex:
        return tex
    # Remove standalone lines that are just \pause (optionally with [..]) and trailing comments.
    tex = re.sub(r'(?m)^\s*\\pause(?:\s*\[[^\]]*\])?\s*(?:%[^\n]*)?\n?', '', tex)
    # Remove any remaining inline \pause occurrences.
    tex = re.sub(r'\\pause(?:\s*\[[^\]]*\])?', '', tex)
    # Neaten spacing
    #tex = re.sub(r'\n{3,}', '\n\n', tex).strip()
    return tex


#def gen_slide(llmmodel, model_name):
#print(f"[INFO] Configuring LLM client for model: {model_choice}")

if model_choice == 'gemini':
    client = genai.Client(api_key=api_key)
elif model_choice == 'openai':
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
elif model_choice == 'deepseek':
    client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
else:
    raise ValueError("Unsupported LLM model")

def load_pdf(fp):
    print(f"[INFO] Loading PDF: {fp}")
    import fitz
    doc = fitz.open(fp)
    try:
        pages = [(page.get_text("text") or "") for page in doc]
    finally:
        doc.close()
    content = "\n".join(pages)
    print(f"[INFO] Loaded {len(pages)} pages, {len(content)} chars.")
    return content

pdf_content = load_pdf('source.pdf')

# Read the prompt content from external file
prompt_file = "gen_slides_prompt_v20_hybrid.txt"
# prompt_file = "gen_slides_prompt_thesis.txt"

prompt_path = Path(__file__).resolve().parent / prompt_file
with open(prompt_path, 'r', encoding='utf-8') as pf:
    prompt = pf.read()
# Wrap prompt content and pdf_content
prompt = prompt.replace("{pdf_content}", pdf_content)

print(f"[INFO] Prompt loaded from {prompt_path}")

if model_choice in ('openai', 'deepseek'):
    print(f"[INFO] Sending prompt to {model_choice}")
    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role":"system","content":"You are an AI assistant that generates high-quality LaTeX Beamer slides for physics presentations."},
            {"role":"user","content":prompt}
        ],
        stream=False
    )
    latex_presentation = resp.choices[0].message.content
else:  # gemini
    print("[INFO] Sending prompt to Gemini")
    resp = client.models.generate_content(model=model_name, contents=prompt)
    latex_presentation = resp.text

# Clean code fences
lines = latex_presentation.strip().splitlines()
if lines and lines[0].startswith("```"):
    lines = lines[1:]
if lines and lines[-1].startswith("```"):
    lines = lines[:-1]
latex_presentation = "\n".join(lines)
# Remove any \pause commands to ensure TTS-safe & stable Beamer output
latex_presentation = _strip_pause_commands(latex_presentation)

# OPTION A: keep at most ONE blank line between blocks
#latex_presentation = re.sub(r'(?:[ \t\xA0]*\r?\n){2,}', '\n\n', latex_presentation).strip() + '\n'

# OPTION B (stricter): no blank lines between blocks (single newline only)
latex_presentation = re.sub(r'(?:[ \t\xA0]*\r?\n){2,}', '\n', latex_presentation).strip() + '\n'

out_base = 'slides'
with open(out_base + '.tex','w',encoding='utf-8') as f:
    f.write(latex_presentation)

#normalize_latex_blank_lines_in_place(
#            "slides.tex",
#            keep_one_blank=True,                  # keep one blank line between blocks
#            treat_comment_only_as_blank=True,     # treat '% ...' lines as blank-like
#            preserve_first_comment_in_run=False,  # prefer a blank over keeping comments in separators
#            )

## begin compiling latex after exiting the LLM phase ##
tex_file = out_base + '.tex'
remove_missing_graphics_in_place(tex_file)
clean_pause_in_place(tex_file)
compile_ok = False
for attempt in range(1, 5):
    # Repair passes (especially LLM-assisted repair) may reintroduce blank
    # paragraphs inside equation/align environments. Beamer/TeX treats those
    # as paragraph breaks in math mode and fails later at \end{frame}.
    # Re-apply v6 strict blank-line normalization before every compile attempt.
    _tex_path = Path(tex_file)
    # Strictly remove blank paragraphs before every compile attempt.  Using
    # splitlines() also handles mixed/duplicated CRLF forms that regex-based
    # normalization can miss after AI-assisted repair passes.  A blank line
    # inside display math creates a paragraph break and can surface later as
    # an opaque "Missing $ inserted" error at \end{frame}.
    _tex_raw = _tex_path.read_text(encoding="utf-8-sig")
    _tex_lines = [line.rstrip() for line in _tex_raw.splitlines() if line.strip()]
    _tex_path.write_text("\n".join(_tex_lines) + "\n", encoding="utf-8")
    remove_missing_graphics_in_place(tex_file)
    clean_pause_in_place(tex_file)
    result = subprocess.run(
        ['pdflatex', '-interaction=nonstopmode', '-halt-on-error', tex_file],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    if result.returncode == 0:
        print(f"✅ pdflatex compilation succeeded for '{tex_file}' at attempt {attempt}")
        compile_ok = True
        break
    print(f"❌ pdflatex compilation failed for '{tex_file}' at attempt {attempt}")
    if attempt == 1:
        fix_latex.clean_tex_file(tex_file)
    elif attempt == 2:
        fix_latex.clean_tex_file2(tex_file, model_choice, model_name, api_key)
    elif attempt == 3:
        fix_latex.clean_tex_file(tex_file)
    clean_pause_in_place(tex_file)
if not compile_ok:
    raise RuntimeError(f"Unable to compile {tex_file} after four repair attempts.")
## end of compiling latex after exiting the LLM phase ##

### begin the main program here #######################################################
#print(f"[INFO] Starting slide generation process for model: {model_choice}")
#gen_slide(model_choice,model_name)



print(f"[INFO] Completed slide generation process for model: {model_choice}")
print("[INFO] Cleaning up auxiliary files...")
aux_files = [  "slides_dsk", "slides_gemini", "slides_oai" ]
exts = [".log", ".nav", ".out", ".snm", ".toc", ".aux", ".synctex.gz"]
for base in aux_files:
    for ext in exts:
        try:
            os.remove(base + ext)
            print(f"[INFO] Removed auxiliary file: {base + ext}")
        except:
            pass
print("[INFO] Cleanup of auxiliary files complete.")