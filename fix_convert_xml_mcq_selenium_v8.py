#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# MicroGen_AI Educational Automation Package
# © 2025 Dr. Yoon Tiem Leong, School of Physics, Universiti Sains Malaysia.
#
# This file is part of the MicroGen_AI package.
#
# Licensed under the MIT License (see LICENSE file in the project root).
# You may not use this file except in compliance with the License.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.



import os, re, sys, io, time, glob, socket, shutil, html, traceback, subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

# ---------- adaptive wait ----------
from adaptive_wait import adaptive_send_and_get

# ---------- v75 sanitizer (optional) ----------
try:
    from convert_xml_mcq_v75 import post_sanitize_mcq_file
    HAVE_EXT_SANITIZER = True
except Exception:
    HAVE_EXT_SANITIZER = False

# ---------- Selenium ----------
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException

# ---------- Clipboard (optional) ----------
try:
    import pyperclip
    HAVE_PYPERCLIP = True
except Exception:
    HAVE_PYPERCLIP = False

def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)

# =========================
# Config
# =========================
CHROME_EXE        = os.environ.get("CHROME_EXE", r"C:/Program Files/Google/Chrome/Application/chrome.exe")
CHROME_DEBUG_PORT = int(os.environ.get("CHROME_DEBUG_PORT", "9222"))
USER_DATA_DIR     = os.environ.get("CHROME_USER_DATA", r"C:/tmp/selenium-chrome")
GEMINI_URL        = os.environ.get("GEMINI_APP", "https://gemini.google.com/app")
PRESET            = os.environ.get("GEMINI_PRESET", "long")
EXTRA_WAIT        = int(os.environ["GEMINI_EXTRA_WAIT"]) if os.environ.get("GEMINI_EXTRA_WAIT") else None

QUIET_SECS = int(os.getenv("GEMINI_QUIET_SECS", "8"))
MAX_TAIL   = int(os.getenv("GEMINI_MAX_TAIL", "45"))

DEFAULT_TIMEOUT = 10
PROMPT_BASENAME = "prompts_xml2mcq_v6.txt"

BEGIN = "<<<BEGIN_QUIZ_XML>>>"
END   = "<<<END_QUIZ_XML>>>"

# =========================
# Chrome attach/launch
# =========================
def _is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

def _launch_chrome():
    if not Path(CHROME_EXE).exists():
        raise FileNotFoundError(f"Chrome not found: {CHROME_EXE}")
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    log(f"Launching Chrome port={CHROME_DEBUG_PORT} profile={USER_DATA_DIR}")
    subprocess.Popen([
        CHROME_EXE,
        f"--remote-debugging-port={CHROME_DEBUG_PORT}",
        f"--user-data-dir={USER_DATA_DIR}",
        GEMINI_URL
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.0)

def _attach_or_launch():
    if not _is_port_in_use(CHROME_DEBUG_PORT):
        _launch_chrome()
        t0 = time.time()
        while time.time() - t0 < 20:
            if _is_port_in_use(CHROME_DEBUG_PORT):
                break
            time.sleep(0.3)
        if not _is_port_in_use(CHROME_DEBUG_PORT):
            raise RuntimeError(f"Failed to open Chrome debug port {CHROME_DEBUG_PORT}")

    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{CHROME_DEBUG_PORT}")
    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
    return driver, wait

# =========================
# Gemini UI helpers
# =========================
def wait_present(wait, by, sel, timeout=DEFAULT_TIMEOUT):
    return WebDriverWait(wait._driver, timeout).until(EC.presence_of_element_located((by, sel)))

def wait_clickable(wait, by, sel, timeout=DEFAULT_TIMEOUT):
    return WebDriverWait(wait._driver, timeout).until(EC.element_to_be_clickable((by, sel)))

def open_clean_gemini_chat(driver, wait):
    driver.get(GEMINI_URL)
    log("Opened Gemini")
    time.sleep(0.5)
    try:
        btn = wait_clickable(wait, By.XPATH, '//button[@aria-label="New chat"]')
        btn.click()
        time.sleep(0.3)
        log("Clicked 'New chat'", "OK")
    except Exception:
        log("'New chat' not found; continuing", "WARN")
    try:
        host = wait_present(wait, By.CSS_SELECTOR, 'div[aria-label="Enter a prompt here"]')
        host.click()
    except Exception:
        pass

def _make_file_input_visible(driver, file_input):
    try:
        driver.execute_script("""
            arguments[0].style.visibility='visible';
            arguments[0].style.display='block';
            arguments[0].removeAttribute('hidden');
            arguments[0].removeAttribute('aria-hidden');
        """, file_input)
    except Exception:
        pass


def upload_files_to_gemini(driver, wait, files):
    """
    Robust uploader:
    - Tries multiple attach button variants.
    - Searches for file inputs via XPATH and CSS with retries.
    - Falls back to Chrome DevTools Protocol (CDP) to set files on hidden inputs.
    - Confirms via "attachment chips" heuristic, but does not fail if absent.
    """
    from pathlib import Path as _Path
    import time as _time

    files = [_Path(f).resolve() for f in files]
    for f in files:
        if not f.exists():
            raise FileNotFoundError(f"Missing file: {f}")
    log("Uploading:\n - " + "\n - ".join(str(x) for x in files))

    # 1) Attempt to open attach UI (be tolerant with selectors)
    try:
        attach_candidates = [
            '//button[@aria-label="Open upload file menu"]',
            '//button[@aria-haspopup="menu"]',
            '//button[.//span[contains(translate(text(),"UPLOAD","upload"),"upload")]]',
        ]
        opened = False
        for xp in attach_candidates:
            try:
                b = wait_clickable(wait, By.XPATH, xp)
                b.click()
                _time.sleep(0.25)
                opened = True
                break
            except Exception:
                pass
        if opened:
            try:
                up = wait_clickable(wait, By.XPATH,
                    '//button[contains(@aria-label,"Upload") or .//span[contains(translate(text(),"UPLOAD","upload"),"upload")]]'
                )
                up.click()
                _time.sleep(0.25)
            except Exception:
                pass
        else:
            log("Attach menu button not found; trying direct file input", "WARN")
    except Exception:
        log("Attach UI open step skipped due to UI variant.", "WARN")

    # 2) Locate input[type=file] with retries (XPATH + CSS)
    file_input = None
    selectors = ['//input[@type="file"]', 'input[type="file"]', '//div//input[@type="file"]']
    deadline = time.time() + 8.0
    while time.time() < deadline and file_input is None:
        for sel in selectors:
            try:
                if sel.startswith('//'):
                    file_input = wait_present(wait, By.XPATH, sel)
                else:
                    file_input = wait_present(wait, By.CSS_SELECTOR, sel)
                if file_input:
                    break
            except Exception:
                continue
        if file_input is None:
            time.sleep(0.25)

    # 3) CDP fallback: set files even if input is hidden/shadowed
    if file_input is None:
        try:
            root = driver.execute_cdp_cmd("DOM.getDocument", {"depth": -1})
            node_id = driver.execute_cdp_cmd("DOM.querySelector", {
                "nodeId": root["root"]["nodeId"],
                "selector": "input[type=file]"
            }).get("nodeId")
            if node_id:
                driver.execute_cdp_cmd("DOM.setFileInputFiles", {
                    "files": [str(p) for p in files],
                    "nodeId": node_id
                })
                log("Files set via CDP (no visible input needed).", "OK")
            else:
                raise RuntimeError("No file input found via CDP.")
        except Exception as e:
            raise RuntimeError(f"Could not access file input on Gemini UI (selectors + CDP failed): {e}")
    else:
        try:
            _make_file_input_visible(driver, file_input)
        except Exception:
            pass
        try:
            file_input.send_keys("\n".join(str(p) for p in files))
        except Exception as e:
            try:
                root = driver.execute_cdp_cmd("DOM.getDocument", {"depth": -1})
                node_id = driver.execute_cdp_cmd("DOM.querySelector", {
                    "nodeId": root["root"]["nodeId"],
                    "selector": "input[type=file]"
                }).get("nodeId")
                if node_id:
                    driver.execute_cdp_cmd("DOM.setFileInputFiles", {
                        "files": [str(p) for p in files],
                        "nodeId": node_id
                    })
                    log("Files set via CDP after send_keys failure.", "OK")
                else:
                    raise RuntimeError("No file input found via CDP after send_keys failure.")
            except Exception as e2:
                raise RuntimeError(f"Could not access file input on Gemini UI: {e2}")

    # 4) Heuristic confirmation
    t0 = time.time()
    ok = False
    while time.time() - t0 < 12:
        try:
            chips = driver.find_elements(By.XPATH, '//div[contains(@class,"attachment") or @aria-label="Attachment"]')
            if chips:
                ok = True
                break
        except Exception:
            pass
        time.sleep(0.4)
    log("Attachments appear queued." if ok else "Could not visually confirm attachments; proceeding",
        "OK" if ok else "WARN")
# =========================
# Placeholders for base64 <img>
# =========================
IMG_PATTERN = re.compile(
    r'(<img\b[^>]*\bsrc\s*=\s*["\']data:image/[^;]+;base64,[^"\']+["\'][^>]*>)',
    re.IGNORECASE | re.DOTALL
)
PLACEHOLDER_PREFIX = "%%FIGURE_PLACEHOLDER_"
PLACEHOLDER_SUFFIX = "%%"

def find_and_replace_images_with_placeholders(xml_text: str):
    if not xml_text:
        return xml_text, {}
    placeholders = {}
    idx = 0
    def _repl(m):
        nonlocal idx
        tag = m.group(1)
        ph = f"{PLACEHOLDER_PREFIX}img{idx}{PLACEHOLDER_SUFFIX}"
        placeholders[ph] = tag
        idx += 1
        return ph
    cleaned = IMG_PATTERN.sub(_repl, xml_text)
    return cleaned, placeholders

# ---------- Canonicalize &amp; restore ----------
def _normalize_for_matching(s: str) -> str:
    if not s:
        return s
    s = s.replace("&amp;#37;", "&#37;")
    s = s.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    s = s.replace("\\_", "_").replace("\\％", "％").replace("\\%", "%")
    return s

def _variants_for_placeholder(ph: str, idx: int):
    FIG = r"F\s*I\s*G\s*U\s*R\s*E"
    PLC = r"P\s*L\s*A\s*C\s*E\s*H\s*O\s*L\s*D\s*E\s*R"
    IMG = rf"i\s*m\s*g\s*{idx}"
    SEP = r"[\s_\-\\]*"
    WS  = r"\s*"
    PCT = r"(?:%|％|&#37;)"
    WRAP_L = r"(?:`+|<code>)?"
    WRAP_R = r"(?:`+|</code>)?"

    p1 = rf"{PCT}{WS}{PCT}{WS}{WRAP_L}{FIG}{SEP}{PLC}{SEP}{IMG}{WRAP_R}{WS}{PCT}{WS}{PCT}"
    p2 = rf"{PCT}?{WS}{PCT}?{WS}{WRAP_L}{FIG}{SEP}{PLC}{SEP}{IMG}{WRAP_R}{WS}{PCT}?{WS}{PCT}?"
    p3 = rf"{WRAP_L}{FIG}{SEP}{PLC}{SEP}{IMG}{WRAP_R}"

    p0 = re.escape(ph)
    p0_html = re.escape(ph.replace("%", "&#37;"))
    p0_full = re.escape(ph.replace("%", "％"))

    return [p0, p0_html, p0_full, p1, p2, p3]

def restore_images_bulletproof(text: str, placeholders: dict) -> tuple[str, int, list]:
    if not text or not placeholders:
        return text or "", 0, []
    s = _normalize_for_matching(text)
    total = 0
    unresolved = []

    # Fast exact replacements first
    for ph, tag in placeholders.items():
        for variant in (ph, ph.replace("%", "&#37;"), ph.replace("%", "％")):
            c = s.count(variant)
            if c:
                s = s.replace(variant, tag)
                total += c

    # Tolerant patterns per index
    for ph, tag in placeholders.items():
        m = re.search(r"img(\d+)", ph, flags=re.I)
        if not m:
            continue
        idx = int(m.group(1))
        for pat in _variants_for_placeholder(ph, idx):
            rr = re.compile(pat, re.IGNORECASE | re.DOTALL)
            s2, n = rr.subn(tag, s)
            if n:
                s, total = s2, total + n
        # check if any variant remains
        still = (ph in s) or (ph.replace("%","&#37;") in s) or (ph.replace("%","％") in s)
        if still:
            unresolved.append(ph)

    # Generic catch-all
    if unresolved:
        generic = re.compile(
            r"(?:%|％|&#37;)?\s*(?:%|％|&#37;)?\s*FIGURE[\s_\-\\]*PLACEHOLDER[\s_\-\\]*img\s*(\d+)\s*(?:%|％|&#37;)?\s*(?:%|％|&#37;)?",
            re.IGNORECASE | re.DOTALL
        )
        def repl(m):
            key = f"{PLACEHOLDER_PREFIX}img{int(m.group(1))}{PLACEHOLDER_SUFFIX}"
            return placeholders.get(key, m.group(0))
        s2, n = generic.subn(repl, s)
        if n:
            s = s2
            total += n
            unresolved = [ph for ph in unresolved if (ph in s)]

    return s, total, unresolved

# =========================
# Markers &amp; extraction
# =========================
BEGIN_RE = re.compile(re.escape(BEGIN) + r"(.*?)" + re.escape(END), re.S)

def extract_between_markers(text: str) -> str:
    if not text:
        return ""
    m = BEGIN_RE.search(text)
    return (m.group(1).strip() if m else text.strip())

def extract_code_fence_payload(s: str) -> str:
    if not s:
        return s
    blocks = re.findall(r"```(?:\s*xml)?\s*(.*?)```", s, flags=re.S | re.I)
    if not blocks:
        return s
    with_quiz = [b for b in blocks if "<quiz" in b]
    return (max(with_quiz, key=len) if with_quiz else max(blocks, key=len)).strip()

def find_best_quiz_block(s: str) -> str:
    if not s:
        return ""
    cand = []
    for m in re.finditer(r"<quiz\b", s):
        start = m.start()
        end = s.find("</quiz>", start)
        if end != -1:
            end += len("</quiz>")
            cand.append(s[start:end])
    return (max(cand, key=len).strip() if cand else "")

# =========================
# New: deverbatim (remove Gemini's backslash-escapes)
# =========================
def deverbatim(s: str) -> str:
    if not s:
        return s
    # Remove backslash before XML syntax and common escapes
    s = (s.replace("\\<", "<")
           .replace("\\>", ">")
           .replace("\\/", "/")
           .replace("\\!", "!")
           .replace("\\?", "?")
           .replace("\\[", "[")
           .replace("\\]", "]"))
    # Fix escaped CDATA markers specifically
    s = s.replace("\\<![CDATA[", "<![CDATA[").replace("\\]]>", "]]>")
    # Underscore and percent escapes that break placeholder matching
    s = s.replace("\\_", "_").replace("\\％", "％").replace("\\%", "%")
    # Collapse accidental double backslashes
    s = s.replace("\\\\", "\\")
    return s

# =========================
# Text cleanup and CDATA-aware write
# =========================
_ILLEGAL_XML_CHARS = r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD]"
_BARE_AMP = re.compile(r"&amp;(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9A-Fa-f]+);)")

def clean_xml_content(xml_string: str) -> str:
    s = xml_string or ""
    s = s.replace("\ufeff", "").replace("\u2028", "")
    s = s.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    s = re.sub(_ILLEGAL_XML_CHARS, "", s)
    s = re.sub(r"<\?xml[^>]*\?>", "", s)
    s = _BARE_AMP.sub("&amp;", s)
    return s

class CDATA(str): pass

def _escape_cdata(text):
    try:
        text_str = str(text) if text is not None else ""
        return text_str.replace(']]>', ']]]]><![CDATA[>')
    except Exception:
        return ""

def _write_element_recursive(writer_func, element, encoding, level=0, indent="  "):
    if indent:
        writer_func((indent * level).encode(encoding))
    writer_func(f"<{element.tag}".encode(encoding))
    for key, value in element.attrib.items():
        writer_func(f' {key}="{html.escape(value, quote=True)}"'.encode(encoding))
    has_text = element.text and element.text.strip()
    has_children = len(element) > 0
    if not has_text and not has_children:
        writer_func("/>".encode(encoding))
    else:
        writer_func(">".encode(encoding))
        if has_text:
            if isinstance(element.text, CDATA):
                writer_func(f"<![CDATA[{_escape_cdata(element.text)}]]>".encode(encoding))
            else:
                writer_func(html.escape(element.text).encode(encoding))
        if has_children:
            if indent:
                writer_func("\n".encode(encoding))
            for child in element:
                _write_element_recursive(writer_func, child, encoding, level + 1, indent)
            if indent and has_children:
                writer_func((indent * level).encode(encoding))
        writer_func(f"</{element.tag}>".encode(encoding))
    if indent or level > 0:
        writer_func("\n".encode(encoding))

def write_xml_with_cdata(tree, filename, encoding="utf-8", xml_declaration=True, indent=None):
    filename_str = str(filename)
    if not filename_str:
        print("❌ [ERROR] Attempted write with empty filename.")
        return
    try:
        outdir = os.path.dirname(filename_str)
        if outdir:
            os.makedirs(outdir, exist_ok=True)
        with open(filename_str, "wb") as f:
            if xml_declaration:
                f.write(f'<?xml version="1.0" encoding="{encoding}"?>\n'.encode(encoding))
            _write_element_recursive(f.write, tree.getroot(), encoding, indent=indent or "")
    except Exception as e:
        print(f"❌ [ERROR] Failed XML write '{os.path.basename(filename_str)}': {e}")
        traceback.print_exc()

# Sanitizer for <text> nodes prior to final write
_CDATA_START_VAR = re.compile(r"<\s*!\s*\[\s*CDATA\s*\[", re.IGNORECASE)
_CDATA_END_VAR   = re.compile(r"\]\s*\]\s*>", re.IGNORECASE)
_FENCE_LINE      = re.compile(r"^\s*(```+|~~~+).*$", re.M)

def _strip_outer_lonely_angle_brackets(payload: str) -> str:
    if not payload:
        return payload
    s = payload.strip()
    if s.startswith("<") and s.endswith(">"):
        inner = s[1:-1].strip()
        if "<" not in inner and ">" not in inner and "/" not in inner:
            return inner
    return payload

def _remove_cdata_tokens_variants(s: str) -> tuple[str, int]:
    if not s:
        return s, 0
    count_before = len(_CDATA_START_VAR.findall(s)) + len(_CDATA_END_VAR.findall(s))
    s = _CDATA_START_VAR.sub("", s)
    s = _CDATA_END_VAR.sub("", s)
    count_before += s.count("<![CDATA[") + s.count("]]>")
    s = s.replace("<![CDATA[", "").replace("]]>", "")
    return s, count_before

def sanitize_text_payload(payload: str) -> tuple[str, int]:
    if payload is None:
        payload = ""
    tokens_removed = 0
    payload, removed = _remove_cdata_tokens_variants(payload)
    tokens_removed += removed
    payload = _strip_outer_lonely_angle_brackets(payload)
    payload = _FENCE_LINE.sub("", payload)
    return payload, tokens_removed

def post_sanitize_mcq_text(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    if root.tag != "quiz":
        q = root.find(".//quiz")
        if q is None:
            return xml_text
        root = q
    for t in root.iter("text"):
        payload = t.text or ""
        cleaned, _ = sanitize_text_payload(payload)
        t.text = CDATA(cleaned)
    buf = io.BytesIO()
    def _w(b: bytes): buf.write(b)
    _write_element_recursive(_w, root, 'utf-8', level=0, indent="  ")
    return buf.getvalue().decode('utf-8')

# =========================
# Tail settle + copy helpers
# =========================
def _get_last_assistant_block_text(driver) -> str:
    candidates = [
        '//main//*[contains(@class,"response") or contains(@class,"message")][.//button or .//pre or .//code]',
        '//main//article|//main//section|//main//div[contains(@class,"prose")]'
    ]
    last_text = ""
    for xp in candidates:
        blocks = driver.find_elements(By.XPATH, xp)
        for el in blocks[-4:]:
            try:
                if el.is_displayed():
                    t = el.text or ""
                    if len(t.strip()) > len(last_text.strip()):
                        last_text = t
            except StaleElementReferenceException:
                continue
    return last_text

def _has_active_spinner(driver) -> bool:
    try:
        spinners = driver.find_elements(By.XPATH, '//*[contains(@role,"progressbar") or contains(@class,"spinner")]')
        for s in spinners:
            try:
                if s.is_displayed():
                    return True
            except StaleElementReferenceException:
                continue
    except Exception:
        pass
    try:
        stop_btns = driver.find_elements(By.XPATH, '//button[.//span[contains(text(),"Stop")]]')
        for b in stop_btns:
            if b.is_displayed():
                return True
    except Exception:
        pass
    return False

def _click_copy_and_read(driver) -> str:
    try:
        copy_btns = driver.find_elements(By.XPATH, '//button[@aria-label="Copy" or .//span[text()="Copy"]]')
        for b in reversed(copy_btns):
            if b.is_displayed() and b.is_enabled():
                b.click()
                time.sleep(0.15)
                if HAVE_PYPERCLIP:
                    try:
                        return pyperclip.paste()
                    except Exception:
                        break
    except Exception:
        pass
    return _get_last_assistant_block_text(driver)

def settle_then_copy_latest(driver, base_text: str, quiet_secs: int, max_tail: int) -> str:
    best = base_text or ""
    last_len = len(_get_last_assistant_block_text(driver))
    stable_for = 0
    start = time.time()
    while time.time() - start < max_tail:
        time.sleep(1.0)
        now_txt = _get_last_assistant_block_text(driver)
        now_len = len(now_txt)
        if now_len > last_len:
            last_len = now_len
            stable_for = 0
        else:
            stable_for += 1
        if stable_for >= quiet_secs and not _has_active_spinner(driver):
            break
    final_try = _click_copy_and_read(driver)
    return final_try if len(final_try) > len(best) else best

# =========================
# Snapshots + raw copy helpers
# =========================
def _write_textfile(path: Path, text: str, encoding="utf-8"):
    path.write_text(text or "", encoding=encoding)
    print(f"[OK] Snapshot saved -> {path.name}")

def _snap_base(src_xml: Path) -> Path:
    outdir = src_xml.with_name(src_xml.stem + "__snapshots")
    outdir.mkdir(exist_ok=True)
    return outdir

def _first_between(s: str, start: str, end: str) -> str:
    if not s:
        return ""
    i = s.find(start)
    j = s.rfind(end)
    if i != -1 and j != -1 and j > i:
        return s[i:j+len(end)]
    return ""

def _save_raw_copy(out_path: Path):
    raw_path = out_path.with_name(out_path.stem + "_raw" + out_path.suffix)
    shutil.copyfile(out_path, raw_path)
    log(f"📦 Raw copy saved: {raw_path.name}", "OK")

# =========================
# Utility
# =========================
def find_prompt_file(script_dir: Path) -> Path:
    candidates = [script_dir / PROMPT_BASENAME, Path.cwd() / PROMPT_BASENAME]
    for c in candidates:
        if c.exists():
            return c.resolve()
    raise FileNotFoundError(f"{PROMPT_BASENAME} not found next to script or in CWD.")

# =========================
# Core per-file flow
# =========================
def process_one_file(driver, wait, prompt_file: Path, src_xml: Path):
    # 1) Prepare upload: replace base64 images by placeholders
    src_text = Path(src_xml).read_text(encoding="utf-8")
    stripped_text, placeholders = find_and_replace_images_with_placeholders(src_text)
    tmp_path = src_xml.with_name(src_xml.stem + "__llm_tmp.xml")
    tmp_path.write_text(stripped_text, encoding="utf-8")

    open_clean_gemini_chat(driver, wait)
    upload_files_to_gemini(driver, wait, [prompt_file, tmp_path])

    instruction = (
        "You will see TWO attachments:\n"
        f"  1) Instruction file: {prompt_file.name}\n"
        f"  2) Source questions: {tmp_path.name}\n\n"
        "TASK:\n"
        "- Follow the instructions exactly as written in the attached prompt file.\n"
        "- Apply them to the attached source XML (convert all questions accordingly).\n"
        "- IMPORTANT: Do NOT alter any token like %%FIGURE_PLACEHOLDER_*%%; keep them verbatim.\n"
        "- Output ONLY the final Moodle XML for the whole quiz.\n"
        f"- Return it strictly between these markers:\n{BEGIN}\n<quiz> ... </quiz>\n{END}\n"
        "Do not include any commentary or code fences."
    )

    overrides = {}
    if EXTRA_WAIT:
        overrides["max_wait"] = EXTRA_WAIT

    log("Submitting instruction ...")
    raw_first = adaptive_send_and_get(
        driver, instruction, preset=PRESET,
        overrides=(overrides or None),
        strip_code_fences=True, latex_only=False
    )
    raw = settle_then_copy_latest(driver, raw_first, QUIET_SECS, MAX_TAIL)

    # 2) Snapshots of raw and between markers
    snaps = _snap_base(src_xml)
    _write_textfile(snaps / "00_raw_response.txt", raw)
    between = extract_between_markers(raw).strip()
    _write_textfile(snaps / "01_between_markers.txt", between)
    quiz_candidate = _first_between(between, "<quiz", "</quiz>") or _first_between(raw, "<quiz", "</quiz>")
    _write_textfile(snaps / "02_quiz_candidate.xml", quiz_candidate)

    # 3) Build robust payload (deverbatim → unescape → clean)
    payload = (quiz_candidate or between or raw or "").strip()
    payload = extract_code_fence_payload(payload)
    payload = deverbatim(payload)          # NEW: remove backslash escapes (e.g., \<quiz\>)  <-- important
    payload = html.unescape(payload)       # NEW: convert &lt; &gt; etc if used
    best_quiz = find_best_quiz_block(payload)
    if best_quiz:
        payload = best_quiz
    payload = clean_xml_content(payload)

    # 4) Restore images after canonicalization/normalization
    payload_restored, restored_count, unresolved = restore_images_bulletproof(payload, placeholders)
    _write_textfile(snaps / "02a_after_restore.xml", payload_restored)
    if placeholders:
        log(f"🖼️ Restored placeholders: {restored_count}/{len(placeholders)}", "OK")
        if unresolved:
            log(f"⚠️ Unresolved placeholders: {', '.join(unresolved)}", "WARN")

    _write_textfile(snaps / "03_preparse_payload.xml", payload_restored)
    out_path = src_xml.with_name(src_xml.stem + "_mcq.xml")

    # 5) Parse, write, preserve raw, then external sanitize
    def _try_parse(text: str) -> str:
        txt = clean_xml_content(text or "")
        s = txt.find("<quiz")
        e = txt.rfind("</quiz>")
        if s != -1 and e != -1 and e > s:
            txt = txt[s:e+len("</quiz>")]
        ET.fromstring(txt)  # may raise
        return txt

    try:
        parseable = _try_parse(payload_restored)
        pre_sanitized = post_sanitize_mcq_text(parseable)
        write_xml_with_cdata(ET.ElementTree(ET.fromstring(pre_sanitized)), out_path,
                             encoding="utf-8", xml_declaration=True, indent="  ")
        log(f"✅ Wrote: {out_path.name}", "OK")
        _write_textfile(snaps / "04_final_written.xml", Path(out_path).read_text(encoding="utf-8"))

        _save_raw_copy(out_path)

        if HAVE_EXT_SANITIZER:
            try:
                changed, nodes, removed = post_sanitize_mcq_file(out_path)
                log(f"🧼 [POST] Sanitized '{out_path.name}': cleaned_nodes={nodes}, tokens_removed={removed}, file_rewritten={changed}", "OK")
            except Exception as se:
                log(f"⚠️ [POST] Sanitization skipped: {se}", "WARN")

    except Exception as e:
        # Fallback writes the cleaned+restored content too (not the raw-with-markers)
        warn = f"<!-- WARNING: parse failed: {e} -->\n"
        fallback = payload_restored if payload_restored else payload
        Path(out_path).write_text(warn + (fallback or ""), encoding="utf-8")
        log(f"⚠️  Parse failed; wrote fallback: {out_path.name}", "WARN")
        _write_textfile(snaps / "04_fallback_written.xml", warn + (fallback or ""))

        _save_raw_copy(out_path)

        if HAVE_EXT_SANITIZER:
            try:
                changed, nodes, removed = post_sanitize_mcq_file(out_path)
                log(f"🧼 [POST] Fallback sanitized '{out_path.name}': cleaned_nodes={nodes}, tokens_removed={removed}, file_rewritten={changed}", "OK")
            except Exception as se:
                log(f"⚠️ [POST] Fallback sanitization skipped: {se}", "WARN")

    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass

def _process_with_retry(driver, wait, prompt_file, src_xml, tries=2):
    last_err = None
    for k in range(tries):
        try:
            if k > 0:
                log(f"Retrying upload for {src_xml.name} (attempt {k+1}/{tries})", "WARN")
                open_clean_gemini_chat(driver, wait)
                time.sleep(0.6)
            process_one_file(driver, wait, prompt_file, src_xml)
            return
        except Exception as e:
            last_err = e
            if "Could not access file input on Gemini UI" not in str(e):
                break
    raise last_err

# =========================
# Main
# =========================
def gen_mcq(xml_files):    
    print(f"[INFO] Running in directory: {script_dir}")
    
    driver, wait = _attach_or_launch()
    total = 0
    errors = 0
    t0 = time.time()

    try:
        for src in sorted(xml_files):
            print("\n" + "="*60)
            log(f"Processing: {src.name}")
            try:
                _process_with_retry(driver, wait, prompt_file, src)
                total += 1
                time.sleep(5)
                print('slept for 5s')
            except Exception as e:
                errors += 1
                log(f"❌ [ERROR] {src.name}: {e}", "ERR")
    finally:
        try: driver.quit()
        except Exception: pass
        # best-effort kill of spawned Chrome with our flags
        try:
            import psutil
            for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
                try:
                    pname = (proc.info["name"] or "").lower()
                    cmd = " ".join(proc.info.get("cmdline") or [])
                    if "chrome.exe" in pname and (
                        f"--remote-debugging-port={CHROME_DEBUG_PORT}" in cmd
                        or f"--user-data-dir={USER_DATA_DIR}" in cmd.replace("\\", "/")
                    ):
                        proc.kill()
                        log(f"Killed spawned Chrome (PID={proc.info['pid']})", "OK")
                except Exception:
                    continue
        except Exception:
            pass

    t1 = time.time()
    print("\n" + "="*60)
    print("Processing complete.")
    print(f"  Total files processed: {total}")
    print(f"  Total errors: {errors}")
    print(f"  Elapsed: {t1 - t0:.2f} s")    
    
    #import sanitize_xml
    sanitize_xml.main("*_problemset_mcq.xml")
    ### end main

### generate *_problemset_mcq.xml for the first time
import sanitize_xml
script_dir = Path(__file__).resolve().parent
try:
    prompt_file = find_prompt_file(script_dir)
    log(f"Using prompt file (to attach): {prompt_file}")
except FileNotFoundError as e:
    print(f"❌ {e}")
    sys.exit(1)


#xml_files = [Path(p) for p in glob.glob(str(script_dir / "*_problemset.xml"))]
#xml_files = [p for p in xml_files if not p.name.endswith("_mcq.xml") and p.is_file()]
#if not xml_files:
#    print("❌ No source files matching '*_problemset.xml' (excluding '*_mcq.xml').")
#    sys.exit(1)    
#print('First attempt to generate *_mcq.xml for',[i.name for i in xml_files])
#gen_mcq(xml_files)
#sanitize_xml.main("*_problemset_mcq.xml")
#print('First attempt to generate *_mcq.xml for',[i.name for i in xml_files],'FINISHES')
#print('')


### generate *_problemset_mcq.xml for the second time, targeted at missed *_problemset_xml
xml_files = [Path(p) for p in glob.glob(str(script_dir / "*_problemset.xml"))]
mcq_files = [Path(p) for p in glob.glob(str(script_dir / "*_problemset_mcq.xml"))]
missed_xml_files = sorted({  script_dir / i.name.split('.xml')[0] for i in xml_files} - { script_dir / i.name.split('_mcq')[0] for i in mcq_files})
templist = [ i.name+'.xml' for i in missed_xml_files ]
missed_xml_files = [ script_dir / i for i in templist]
#print('missed_xml_files ',missed_xml_files)
if missed_xml_files:
    print('Second attempt to generate *_mcq.xml for',[i.name for i in missed_xml_files])
    gen_mcq(missed_xml_files)
    sanitize_xml.main("*_problemset_mcq.xml")
    print('Second attempt to generate *_mcq.xml for',[i.name for i in missed_xml_files], 'FINISHES')
##

print('')

### generate *_problemset_mcq.xml for the third time, targeted at missed *_problemset_xml
xml_files = [Path(p) for p in glob.glob(str(script_dir / "*_problemset.xml"))]
mcq_files = [Path(p) for p in glob.glob(str(script_dir / "*_problemset_mcq.xml"))]
missed_xml_files = sorted({  script_dir / i.name.split('.xml')[0] for i in xml_files} - { script_dir / i.name.split('_mcq')[0] for i in mcq_files})
templist = [ i.name+'.xml' for i in missed_xml_files ]
missed_xml_files = [ script_dir / i for i in templist]
#print('missed_xml_files ',missed_xml_files)
if missed_xml_files:
    print('third attempt to generate *_mcq.xml for',[i.name for i in missed_xml_files])
    gen_mcq(missed_xml_files)
    sanitize_xml.main("*_problemset_mcq.xml")
    print('third attempt to generate *_mcq.xml for',[i.name for i in missed_xml_files], 'FINISHES')
##
