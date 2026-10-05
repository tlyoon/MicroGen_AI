# MicroGen_AI Educational Automation Package
# © 2025 Dr. Yoon Tiem Leong, School of Physics, Universiti Sains Malaysia.
#
# This file is part of the MicroGen_AI package.
#
# Licensed under the MIT License (see LICENSE file in the project root).
# You may not use this file except in compliance with the License.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

# adaptive_wait.py
# Robust adaptive wait + copy helpers for browser-driven LLM UIs (e.g., Gemini)
# - Backwards compatible public APIs:
#     * adaptive_send_and_get(driver, instruction, preset="medium", overrides=None)
#     * adaptive_wait_and_copy(driver, preset="medium", overrides=None)
#     * wait_until_response_stable(driver, ...)
#
# Key improvements:
#   • Wider set of selectors for the last response block
#   • Safer stabilization logic (appear → grow → settle) with jittered polling
#   • Stronger copy strategy: button → JS selection + Ctrl+C → fallback to captured text
#   • Quote normalization + optional code-fence stripping
#   • Optional LaTeX-only extraction (toggleable)
#   • Lightweight logging hooks (no external deps)
#
# Works on Windows/Linux/Mac. Requires: selenium, pyperclip (optional but recommended).

from __future__ import annotations
import time, random, math
from typing import Dict, Any, Tuple, Optional

import pyperclip
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# ----------------------
# Tunable presets
# ----------------------
PRESETS: Dict[str, Dict[str, Any]] = {
    "short":  {"max_wait": 60, "stable_secs": 3.0, "min_chars": 30,  "poll_appear": 0.35, "poll_grow": 0.45},
    "medium": {"max_wait": 120, "stable_secs": 5.0, "min_chars": 100, "poll_appear": 0.35, "poll_grow": 0.45},
    "long":   {"max_wait": 200, "stable_secs": 7.5, "min_chars": 140, "poll_appear": 0.40, "poll_grow": 0.55},
}

# ----------------------
# Lightweight logging
# ----------------------
def _log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")

# ----------------------
# Helpers
# ----------------------

# --- Back-compat shims for older callers expecting get_baselines/_wait_for_new_response ---

def get_baselines(driver):
    """
    Return a lightweight snapshot of the last visible assistant block.
    We encode the element identity and current text length.
    """
    try:
        el, txt = _get_last_response_text(driver)
    except Exception:
        el, txt = None, ""
    # Two values to match older call sites' tuple-unpack
    return (id(el) if el else None, len(txt or ""))

def _wait_for_new_response(driver, prev_blocks, prev_copies, timeout: float = 45.0, debounce: float = 0.8) -> bool:
    """
    Polls for a *new* assistant answer relative to the provided baseline.
    Consider it 'new' if either the element identity changes or the text length increases
    by a meaningful amount, and then remains stable for `debounce` seconds.
    """
    import time
    t0 = time.time()
    last_seen_len = None
    last_change = t0

    prev_el_id = prev_blocks if isinstance(prev_blocks, int) else None
    prev_len = int(prev_copies) if isinstance(prev_copies, (int, float)) else 0

    # Phase 1: detect change
    while time.time() - t0 < timeout:
        el, txt = _get_last_response_text(driver)
        cur_id = id(el) if el is not None else None
        cur_len = len(txt or "")
        changed = (cur_id is not None and cur_id != prev_el_id) or (cur_len > max(prev_len, 0) + 10)
        if changed:
            last_seen_len = cur_len
            last_change = time.time()
            break
        time.sleep(0.2)

    if last_seen_len is None:
        return False  # never observed a new block

    # Phase 2: wait for short stability (debounce)
    while time.time() - t0 < timeout:
        _, txt = _get_last_response_text(driver)
        cur_len = len(txt or "")
        if cur_len != last_seen_len:
            last_seen_len = cur_len
            last_change = time.time()
        if time.time() - last_change >= debounce:
            return True
        time.sleep(0.2)

    return True  # treat as success even if we hit the overall timeout after change


def _jitter(base: float, pct: float = 0.15) -> float:
    """Return base ±pct jitter to avoid lockstep polling."""
    delta = base * pct
    return max(0.05, base + random.uniform(-delta, delta))

def _normalize_quotes(s: str) -> str:
    return (s.replace("\u201c", '"')
             .replace("\u201d", '"')
             .replace("\u2019", "'")
             .replace("\u2018", "'")
             .strip())

def _strip_code_fences(s: str) -> str:
    lines = s.strip().splitlines()
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].rstrip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()

def _js_inner_text(driver, element) -> str:
    try:
        return driver.execute_script("return arguments[0].innerText || arguments[0].textContent || '';", element) or ""
    except Exception:
        try:
            return (element.text or "")
        except Exception:
            return ""

def _visible(el) -> bool:
    try:
        return el.is_displayed()
    except Exception:
        return False

# ----------------------
# DOM targeting
# ----------------------
# Copy button candidates (Gemini/others change often)
_COPY_BUTTON_XPATHS = [
    '//button[@aria-label="Copy"]',
    '//button[.//span[text()="Copy"]]',
    '//button[contains(@class,"copy") or contains(@aria-label,"copy") or .//*[contains(text(),"Copy")]]'
]

# “Latest answer” blocks, broad net (order matters)
_RESPONSE_SELECTORS = [
    (By.XPATH,  '//div[@data-md-type]'),
    (By.CSS_SELECTOR, 'div.markdown, div.prose'),
    (By.XPATH,  '//div[contains(@class,"prose") or contains(@class,"markdown")]'),
    (By.XPATH,  '//div[contains(@class,"response")]'),
    (By.CSS_SELECTOR, 'article, section[role="region"][aria-live], div[role="region"][aria-live]')
]

# Composer (Gemini)
_COMPOSER_CANDIDATES = [
    (By.CSS_SELECTOR, 'div[aria-label="Enter a prompt here"]'),
    (By.CSS_SELECTOR, 'textarea[aria-label], div[contenteditable="true"][aria-label]'),
    (By.XPATH, '//div[@contenteditable="true" and @role="textbox"]')
]

def _find_copy_button(driver):
    for xp in _COPY_BUTTON_XPATHS:
        try:
            btns = driver.find_elements(By.XPATH, xp)
            vis = [b for b in btns if _visible(b)]
            if vis:
                return vis[-1]
        except Exception:
            pass
    return None

def _find_last_response_element(driver):
    els = []
    for by, sel in _RESPONSE_SELECTORS:
        try:
            els.extend(driver.find_elements(by, sel))
        except Exception:
            pass
    els = [e for e in els if _visible(e)]
    return els[-1] if els else None

def _get_last_response_text(driver) -> Tuple[Optional[object], str]:
    el = _find_last_response_element(driver)
    if not el:
        return None, ""
    txt = _js_inner_text(driver, el).strip()
    return el, txt

# ----------------------
# Stabilization logic
# ----------------------
def wait_until_response_stable(driver,
                               max_wait: float = 240.0,
                               stable_secs: float = 5.0,
                               min_chars: int = 80,
                               poll_appear: float = 0.35,
                               poll_grow: float = 0.45,
                               require_increase: bool = True) -> str:
    """
    Phase 1: wait for first meaningful block (>= min_chars).
    Phase 2: track growth until there's no change for stable_secs.
    Returns last captured text (may be partial if timeout).
    """
    t0 = time.time()
    last_len = 0
    last_change = t0
    last_text = ""

    # Phase 1 — wait to appear
    while time.time() - t0 < max_wait:
        _, txt = _get_last_response_text(driver)
        if len(txt) >= min_chars:
            last_text = txt
            last_len = len(txt)
            last_change = time.time()
            break
        time.sleep(_jitter(poll_appear))
    else:
        # Never reached min_chars; return whatever we saw (likely empty)
        return last_text

    # Phase 2 — watch for growth and settle
    while time.time() - t0 < max_wait:
        _, txt = _get_last_response_text(driver)
        cur_len = len(txt)
        if cur_len > last_len or (not require_increase and cur_len != last_len):
            last_len = cur_len
            last_text = txt
            last_change = time.time()
        if time.time() - last_change >= stable_secs:
            return last_text
        time.sleep(_jitter(poll_grow))
    return last_text

# ----------------------
# Copy strategies
# ----------------------
def _copy_via_button(driver, expected_len: int, min_chars: int) -> Optional[str]:
    try:
        btn = _find_copy_button(driver)
        if not btn:
            return None
        # Clear clipboard first (best-effort)
        try:
            pyperclip.copy("")
        except Exception:
            pass
        btn.click()
        time.sleep(0.8)
        clip = pyperclip.paste() or ""
        if len(clip.strip()) >= max(int(expected_len * 0.8), min_chars):
            return _normalize_quotes(clip)
    except Exception:
        pass
    return None

def _copy_via_select_all(driver, element) -> Optional[str]:
    """Try JS selection + Ctrl+C to system clipboard."""
    try:
        driver.execute_script("""
            const range = document.createRange();
            range.selectNodeContents(arguments[0]);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
        """, element)
        time.sleep(0.05)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys('c').key_up(Keys.CONTROL).perform()
        time.sleep(0.35)
        clip = pyperclip.paste() or ""
        if clip.strip():
            return _normalize_quotes(clip)
    except Exception:
        pass
    return None

def copy_via_button_or_fallback(driver, stabilized_text: str, min_chars: int = 80) -> str:
    expected_len = len(stabilized_text)
    # Attempt 1: official copy button
    clip = _copy_via_button(driver, expected_len, min_chars)
    if clip:
        return clip

    # Attempt 2: JS select + Ctrl+C on last response element
    el = _find_last_response_element(driver)
    if el:
        clip = _copy_via_select_all(driver, el)
        if clip and len(clip) >= max(int(expected_len * 0.7), min_chars):
            return clip

    # Fallback: return observed text
    return _normalize_quotes(stabilized_text)

# ----------------------
# Public API
# ----------------------
def adaptive_wait_and_copy(driver, preset: str = "medium", overrides: Dict[str, Any] | None = None,
                           strip_code_fences: bool = True, latex_only: bool = False) -> str:
    p = dict(PRESETS.get(preset, PRESETS["medium"]))
    if overrides:
        p.update(overrides)

    stabilized = wait_until_response_stable(
        driver,
        max_wait=p["max_wait"],
        stable_secs=p["stable_secs"],
        min_chars=p["min_chars"],
        poll_appear=p["poll_appear"],
        poll_grow=p["poll_grow"],
    )

    text = copy_via_button_or_fallback(driver, stabilized, min_chars=p["min_chars"])

    if strip_code_fences:
        text = _strip_code_fences(text)

    if latex_only:
        # Extract only LaTeX if the model wrapped it or mixed in prose.
        # Heuristic: take the longest block between \documentclass and \end{document}, else fallback.
        lower = text.lower()
        start = lower.find("\\documentclass")
        end = lower.rfind("\\end{document}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + len("\\end{document}")]
    return text

def _find_composer(driver):
    for by, sel in _COMPOSER_CANDIDATES:
        try:
            els = driver.find_elements(by, sel)
            for e in els:
                if _visible(e):
                    return e
        except Exception:
            pass
    raise RuntimeError("Composer area not found; UI may have changed.")

def adaptive_send_and_get(driver, instruction: str, preset: str = "medium",
                          overrides: Dict[str, Any] | None = None,
                          strip_code_fences: bool = True, latex_only: bool = False) -> str:
    """
    Type the instruction into the composer (preserving newlines),
    submit, then wait/copy the stabilized response.
    """
    host = _find_composer(driver)
    host.click()
    # Send lines with Shift+Enter to keep line breaks, then Enter to submit.
    for i, line in enumerate(instruction.split("\n")):
        if line:
            host.send_keys(line)
        if i < len(instruction.split("\n")) - 1:
            host.send_keys(Keys.SHIFT, Keys.ENTER)  # newline without submit
    host.send_keys(Keys.RETURN)

    return adaptive_wait_and_copy(
        driver, preset=preset, overrides=overrides,
        strip_code_fences=strip_code_fences, latex_only=latex_only
    )
