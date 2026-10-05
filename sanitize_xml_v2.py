#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# MicroGen_AI Educational Automation Package
# © 2025 Dr. Yoon Tiem Leong, School of Physics, Universiti Sains Malaysia.
#
# This file is part of the MicroGen_AI package.
#
# Licensed under the MIT License (see LICENSE file in the project root).
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

"""
sanitize_xml.py (v2)
Sanitize Moodle Question Bank XML files (CLI or programmatic).

Key features:
- Repairs missing <text> wrapper around CDATA.
- Repairs broken CDATA openers [CDATA[ → <![CDATA[.
- Removes XML 1.0–invalid control characters.
- Normalizes risky Unicode typography (Greek handled by policy).
- Escapes stray '&' outside valid entities and outside CDATA.
- Parses once; if ok, normalizes misspelled <question type="..."> values.
- Re-serializes ONLY when the XML tree is changed.
- Renames files that still fail to parse to *__error.xml
- NEW: upgrades ASCII math (^/_/sqrt()) to HTML/Unicode within <text>.
"""

import sys
import os
import re
import time
import glob
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any
import xml.etree.ElementTree as ET

# ---------- Config flags ----------
#   GREEK_POLICY=keep   → keep Unicode (Δ, θ, …)   [default]
#   GREEK_POLICY=entity → map to HTML entities (&Delta;, &theta;, …)
#   GREEK_POLICY=ascii  → transliterate to words ("Delta", "theta", …)
GREEK_POLICY = os.getenv("GREEK_POLICY", "keep").lower().strip()
if GREEK_POLICY not in ("keep", "entity", "ascii"):
    GREEK_POLICY = "keep"

# ---------- Defaults ----------
DEFAULT_PATTERNS = ["*_problemset_mcq.xml", "*_problemset.xml"]

TYPE_TYPO_MAP = {
    "multichoichoice": "multichoice",
    "multichoise": "multichoice",
    "multihoice": "multichoice",
}

# Replace risky unicode that often breaks strict Moodle importers
# NOTE: Greek letters are handled by GREEK_POLICY, not here.
RISKY_REPLACEMENTS = {
    # spaces
    "\u00A0": " ",  # NBSP
    "\u2000": " ", "\u2001": " ", "\u2002": " ", "\u2003": " ", "\u2004": " ",
    "\u2005": " ", "\u2006": " ", "\u2007": " ", "\u2008": " ", "\u2009": " ",
    "\u200A": " ", "\u202F": " ", "\u205F": " ", "\u3000": " ",

    # zero-width / BOM / joiners
    "\u200B": "", "\u200C": "", "\u200D": "", "\ufeff": "", "\u2060": "",

    # bidi/formatting
    "\u200E": "", "\u200F": "", "\u202A": "", "\u202B": "", "\u202C": "",
    "\u202D": "", "\u202E": "", "\u2066": "", "\u2067": "", "\u2068": "", "\u2069": "",

    # hyphens/dashes/minus
    "\u00AD": "-",  # soft hyphen
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2015": "-",
    "\u2212": "-",  # real minus

    # quotes/apostrophes/primes
    "\u2018": "'", "\u2019": "'", "\u201A": ",", "\u201B": "'",
    "\u201C": '"', "\u201D": '"', "\u201E": '"', "\u00AB": '"', "\u00BB": '"',
    "\u2032": "'", "\u2035": "'",   # prime
    "\u2033": '"', "\u2036": '"',   # double prime

    # bullets / dots / ellipses
    "\u2022": "-", "\u2043": "-",
    "\u00B7": ".", "\u2219": ".", "\u22C5": ".", "\u2024": ".", "\u2027": ".",
    "\u2025": "..", "\u2026": "...",

    # math operators / relations (keep √ visual by mapping to entity, not 'sqrt')
    "\u00D7": "x",     # multiply
    "\u00F7": "/",     # divide
    "\u00B1": "+/-", "\u2213": "-/+",
    "\u2264": "<=", "\u2265": ">=", "\u2260": "!=", "\u2248": "~", "\u2245": "~",
    "\u2261": "==",
    "\u221A": "&radic;",  # √
    "\u222B": "integral", "\u222C": "double integral", "\u222E": "contour integral",
    "\u2211": "sum", "\u220F": "prod",
    "\u2202": "partial", "\u2207": "nabla",
    "\u221E": "infinity",
    "\u2227": "and", "\u2228": "or", "\u00AC": "not",
    "\u2229": "cap", "\u222A": "cup",
    "\u2282": "subset", "\u2283": "superset", "\u2286": "subseteq", "\u2287": "supseteq",
    "\u2208": "in", "\u2209": "notin",
    "\u2225": "parallel", "\u27C2": "perp", "\u2223": "|",
    "\u2236": ":", "\u2044": "/",

    # arrows
    "\u2192": "->", "\u2190": "<-", "\u2191": "^", "\u2193": "v",
    "\u2194": "<->", "\u21D2": "=>", "\u21D4": "<=>",

    # degrees / temperature
    "\u00B0": " degrees ", "\u2103": " degC ", "\u2109": " degF ",

    # misc tech
    "\u2126": "ohm", "\u212A": "K", "\u212B": "Angstrom", "\u00B5": "u", "\u2113": "l",

    # currency
    "\u00A3": "GBP", "\u20AC": "EUR", "\u00A5": "JPY", "\u20B9": "INR",
    "\u20A9": "KRW", "\u00A2": "cent", "\u20AB": "VND", "\u20BD": "RUB", "\u20AA": "ILS",

    # superscripts/subscripts in Unicode → ASCII hints
    "\u2070": "^0", "\u00B9": "^1", "\u00B2": "^2", "\u00B3": "^3",
    "\u2074": "^4", "\u2075": "^5", "\u2076": "^6", "\u2077": "^7", "\u2078": "^8", "\u2079": "^9",
    "\u2080": "_0", "\u2081": "_1", "\u2082": "_2", "\u2083": "_3", "\u2084": "_4",
    "\u2085": "_5", "\u2086": "_6", "\u2087": "_7", "\u2088": "_8", "\u2089": "_9",
    "\u207B": "^-",
    "\u221D": "propto",
}

# Greek map (handled per policy)
GREEK_UPPER = {
    "\u0394": ("&Delta;", "Delta"),   # Δ
    "\u0398": ("&Theta;", "Theta"),   # Θ
    "\u03A9": ("&Omega;", "Omega"),   # Ω
}
GREEK_LOWER = {
    "\u03B4": ("&delta;", "delta"),   # δ
    "\u03B8": ("&theta;", "theta"),   # θ
    "\u03C0": ("&pi;",    "pi"),      # π
}

# Disallowed XML 1.0 control characters (except TAB, LF, CR)
CTRL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
VALID_ENTITY = re.compile(r"&(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9A-Fa-f]+);")

# ---------- Pre-salvage for defective files ----------
NOISE_PATTERNS = [
    r"^\s*```.*?$",
    r"^\s*```\s*$",
    r"^\s*<<<\s*BEGIN_QUIZ_XML\s*>>>.*?$",
    r"^\s*<<<\s*END_QUIZ_XML\s*>>>.*?$",
    r"^\s*BEGIN_QUIZ_XML\s*$",
    r"^\s*END_QUIZ_XML\s*$",
    r"^\s*Here is the XML.*?$",
    r"^\s*<\?xml[^>]*>\s*$",
]
NOISE_REGEXES = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in NOISE_PATTERNS]

def strip_non_xml_noise(text: str) -> str:
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    for rgx in NOISE_REGEXES:
        text = rgx.sub("", text)
    first_lt = text.find("<")
    if first_lt > 0:
        text = text[first_lt:]
    last_gt = text.rfind(">")
    if last_gt != -1 and last_gt + 1 < len(text):
        text = text[:last_gt + 1]
    return text.strip()

def extract_or_wrap_quiz(text: str) -> str:
    m = re.search(r"<quiz\b.*?</quiz>", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(0).strip()
    qs = re.findall(r"<question\b.*?</question>", text, flags=re.DOTALL | re.IGNORECASE)
    if qs:
        inner = "\n".join(qs)
        return f"<quiz>\n{inner}\n</quiz>"
    return text.strip()

def fix_unclosed_cdata(text: str) -> str:
    text = re.sub(r"<!\s*\[CDATA\[", "<![CDATA[", text)
    text = re.sub(r"\]\]\s*>", "]]>", text)
    opens = len(re.findall(r"<!\[CDATA\[", text))
    closes = len(re.findall(r"\]\]>", text))
    if opens > closes:
        text = text + ("]]>" * (opens - closes))
    return text


# ---------- Helpers ----------
def find_cdata_regions(text: str) -> List[Tuple[int, int]]:
    regions = []
    start = 0
    while True:
        s = text.find("<![CDATA[", start)
        if s == -1:
            break
        e = text.find("]]>", s)
        if e == -1:
            regions.append((s, len(text)))
            break
        regions.append((s, e + 3))
        start = e + 3
    return regions

def indexes_outside_regions(text: str, pattern: re.Pattern, regions: List[Tuple[int, int]]) -> List[int]:
    hits = []
    for m in pattern.finditer(text):
        start, _ = m.span()
        if not any(rs <= start < re_ for rs, re_ in regions):
            hits.append(start)
    return hits

def line_col_from_pos(text: str, pos: int) -> Tuple[int, int]:
    line = text.count("\n", 0, pos) + 1
    last_nl = text.rfind("\n", 0, pos)
    col = pos - (0 if last_nl == -1 else last_nl + 1) + 1
    return line, col


# ---------- Structural repairs: wrap CDATA with <text> ----------
def _fix_missing_text_wrapper_for_tag(xml: str, tag: str) -> Tuple[str, int]:
    count = 0
    pattern_a = re.compile(
        rf'(<{tag}\b[^>]*>)(\s*)<!\[CDATA\[(.*?)\]\]>(\s*)</text>(\s*)</{tag}>',
        re.DOTALL | re.IGNORECASE
    )
    def repl_a(m):
        nonlocal count
        count += 1
        open_tag = m.group(1)
        cdata = m.group(3)
        return f"{open_tag}<text><![CDATA[{cdata}]]></text></{tag}>"
    xml = pattern_a.sub(repl_a, xml)

    pattern_b = re.compile(
        rf'(<{tag}\b[^>]*>)(\s*)<!\[CDATA\[(.*?)\]\]>(\s*)</{tag}>',
        re.DOTALL | re.IGNORECASE
    )
    def repl_b(m):
        nonlocal count
        count += 1
        open_tag = m.group(1)
        cdata = m.group(3)
        return f"{open_tag}<text><![CDATA[{cdata}]]></text></{tag}>"
    xml = pattern_b.sub(repl_b, xml)
    return xml, count

def fix_malformed_blocks(xml: str) -> Tuple[str, Dict[str, int]]:
    totals: Dict[str, int] = {}
    for tag in (
        "questiontext",
        "generalfeedback",
        "feedback",
        "correctfeedback",
        "partiallycorrectfeedback",
        "incorrectfeedback",
        "hint",
        "name",
        "answer",
    ):
        xml, n = _fix_missing_text_wrapper_for_tag(xml, tag)
        totals[tag] = n
    return xml, totals

def normalize_question_types(root: ET.Element, report: Dict[str, Any]) -> int:
    fixes = 0
    for q in root.findall("./question"):
        t = q.get("type")
        if not t:
            continue
        t_stripped = t.strip()
        t_lower = t_stripped.lower()
        if t_lower in TYPE_TYPO_MAP:
            q.set("type", TYPE_TYPO_MAP[t_lower])
            fixes += 1
        elif t != t_lower:
            q.set("type", t_lower)
            fixes += 1
    if fixes:
        report["issues"].append({
            "severity": "WARN",
            "kind": "QUESTION_TYPE_TYPO",
            "msg": f"Normalized/fixed {fixes} question type value(s).",
        })
        report["changed"] = True
    return fixes


# ---------- Sanitization ----------
def sanitize_text(text: str) -> Tuple[str, Dict[str, Any]]:
    """
    Return (cleaned_text, report) with:
      - CDATA-><text> repairs for required tags
      - Broken [CDATA[ opener repair
      - Removal of invalid control chars
      - Risky unicode normalized (Greek via policy)
      - Stray & escaped
      - XML parsing verified + light Moodle checks
      - NEW: upgrade ASCII math (^/_/sqrt()) to HTML/Unicode in <text>
    """
    report: Dict[str, Any] = {
        "issues": [],
        "unicode_replacements": {},
        "changed": False,
        "structural_fixes": {}
    }

    # 0) PRE-SALVAGE
    original_len = len(text)
    text0 = strip_non_xml_noise(text)
    text1 = extract_or_wrap_quiz(text0)
    text2 = fix_unclosed_cdata(text1)
    if text2 != text:
        report["issues"].append({
            "severity": "WARN",
            "kind": "SALVAGE",
            "msg": f"Applied pre-salvage cleanup (len {original_len} -> {len(text2)})."
        })
        report["changed"] = True
    text = text2

    # 1) STRUCTURAL
    fixed, counts = fix_malformed_blocks(text)
    if counts and any(counts.values()):
        report["issues"].append({
            "severity": "WARN",
            "kind": "STRUCTURAL_REPAIR",
            "msg": "Wrapped CDATA with <text> in: " + ", ".join([f"{k}={v}" for k, v in counts.items() if v])
        })
        report["changed"] = True
    text = fixed
    report["structural_fixes"] = counts or {}

    # 2) Repair broken CDATA opener
    BROKEN_CDATA_OPEN = re.compile(r'(<text\b[^>]*>)\s*\[CDATA\[(.*?)\]\]>\s*</text>', re.DOTALL)
    text_before = text
    text = BROKEN_CDATA_OPEN.sub(r'\1<![CDATA[\2]]></text>', text)
    if text != text_before:
        report["issues"].append({
            "severity": "WARN",
            "kind": "CDATA_OPEN_FIX",
            "msg": "Repaired [CDATA[ → <![CDATA[ in one or more <text> blocks."
        })
        report["changed"] = True

    # 3) Strip UTF-8 BOM
    if text.startswith("\ufeff"):
        report["issues"].append({"severity": "WARN", "kind": "BOM", "msg": "UTF-8 BOM detected at file start."})
        text = text.lstrip("\ufeff")
        report["changed"] = True

    # 4) CDATA balance check
    open_count = text.count("<![CDATA[")
    close_count = text.count("]]>")
    if open_count != close_count:
        report["issues"].append({
            "severity": "ERROR",
            "kind": "CDATA_BALANCE",
            "msg": f"Unbalanced CDATA sections: openings={open_count}, closings={close_count}."
        })

    # 5) Remove XML 1.0 control characters
    CTRL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
    ctrl_hits = list(CTRL_CHARS_PATTERN.finditer(text))
    if ctrl_hits:
        for m in ctrl_hits:
            pos = m.start()
            ch = repr(text[pos])
            line, col = line_col_from_pos(text, pos)
            report["issues"].append({
                "severity": "ERROR",
                "kind": "CTRL_CHAR",
                "msg": f"Disallowed control char {ch} at line {line}, col {col}."
            })
        text = CTRL_CHARS_PATTERN.sub("", text)
        report["changed"] = True

    # 6) Replace risky Unicode typography (EXCLUDING Greek)
    for k, v in RISKY_REPLACEMENTS.items():
        cnt = text.count(k)
        if cnt:
            report["unicode_replacements"][k] = cnt
            report["issues"].append({
                "severity": "WARN",
                "kind": "UNICODE_SYMBOL",
                "msg": f"Found {cnt}x {repr(k)}; replacing with {repr(v)}."
            })
            text = text.replace(k, v)
            report["changed"] = True

    # 6a) Greek handling per policy
    def _apply_greek_policy(payload: str) -> str:
        if GREEK_POLICY == "keep":
            return payload
        if GREEK_POLICY == "entity":
            for ch, (ent, ascii_) in {**GREEK_UPPER, **GREEK_LOWER}.items():
                payload = payload.replace(ch, ent)
            return payload
        # ascii
        for ch, (ent, ascii_) in {**GREEK_UPPER, **GREEK_LOWER}.items():
            payload = payload.replace(ch, ascii_)
        return payload

    new_text = _apply_greek_policy(text)
    if new_text != text:
        changes = sum(text.count(ch) for ch in {**GREEK_UPPER, **GREEK_LOWER}.keys())
        if changes:
            report["issues"].append({
                "severity": "WARN",
                "kind": "GREEK_POLICY",
                "msg": f"Applied Greek policy='{GREEK_POLICY}' on {changes} occurrence(s)."
            })
            report["changed"] = True
    text = new_text

    # 7) Escape stray '&' outside CDATA (and outside known entities)
    regions = find_cdata_regions(text)
    amp_positions = indexes_outside_regions(text, re.compile(r"&"), regions)
    stray_positions = []
    for pos in amp_positions:
        segment = text[pos:pos + 24]
        if not VALID_ENTITY.match(segment):
            stray_positions.append(pos)
    if stray_positions:
        for pos in stray_positions:
            line, col = line_col_from_pos(text, pos)
            report["issues"].append({
                "severity": "ERROR",
                "kind": "STRAY_AMP",
                "msg": f"Unescaped '&' at line {line}, col {col} (outside valid entity)."
            })
        text = re.sub(r"&(?!(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9A-Fa-f]+);)", "&amp;", text)
        report["changed"] = True

    # 8) Parse once, then semantic fixes / checks (+ ASCII math upgrade)
    parse_ok = True
    root = None
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        parse_ok = False
        report["issues"].append({"severity": "ERROR", "kind": "XML_PARSE", "msg": str(e)})
    report["parse_ok"] = parse_ok

    if parse_ok and root is not None:
        tree_changed = False

        if normalize_question_types(root, report):
            tree_changed = True

        # --- Upgrade ASCII math to HTML/Unicode in all <text> payloads ---
        def _upgrade_ascii_math(payload: str) -> str:
            if not payload:
                return payload
            # braced first, then digit/letter; subscripts; sqrt()
            payload = re.sub(r'(?<=\w|\))\^\{([^}]+)\}', r'<sup>\1</sup>', payload)
            payload = re.sub(r'(?<=\w|\))\^(\d+)',        r'<sup>\1</sup>', payload)
            payload = re.sub(r'(?<=\w|\))\^([A-Za-z])',   r'<sup>\1</sup>', payload)
            payload = re.sub(r'([A-Za-z])_\{([^}]+)\}',   r'\1<sub>\2</sub>', payload)
            payload = re.sub(r'([A-Za-z])_([A-Za-z0-9])', r'\1<sub>\2</sub>', payload)
            payload = re.sub(r'\bsqrt\s*\(\s*([^()]+?)\s*\)', r'√(\1)', payload)  # or &radic;
            payload = payload.replace('(1/2)', '½')
            payload = re.sub(r'\bDelta([A-Za-z])', 'Δ\\1', payload)
            payload = re.sub(r'\bdelta([A-Za-z])', 'δ\\1', payload)
            return payload

        changed_math = False
        for t in root.iter("text"):
            old = t.text or ""
            new_txt = _upgrade_ascii_math(old)
            if new_txt != old:
                t.text = new_txt
                changed_math = True

        if changed_math:
            report["issues"].append({
                "severity":"WARN",
                "kind":"ASCII_MATH_UPGRADED",
                "msg":"Upgraded ASCII ^/_/sqrt() to HTML/Unicode in <text> nodes."
            })
            tree_changed = True

        if tree_changed:
            text = ET.tostring(root, encoding="unicode")

        # Light Moodle sanity checks
        try:
            if root.tag != "quiz":
                report["issues"].append({
                    "severity": "WARN",
                    "kind": "ROOT_TAG",
                    "msg": f"Root tag is '{root.tag}', expected 'quiz'."
                })
            q_elems = root.findall("./question")
            missing = 0
            for q in q_elems:
                name = q.findtext("./name/text")
                qtext = q.findtext("./questiontext/text")
                if name is None or qtext is None:
                    missing += 1
            if not q_elems:
                report["issues"].append({"severity": "WARN", "kind": "NO_QUESTIONS", "msg": "No <question> elements found."})
            elif missing:
                report["issues"].append({
                    "severity": "WARN",
                    "kind": "QUESTION_FIELDS",
                    "msg": f"{missing} question(s) missing <name> or <questiontext>."
                })
        except Exception as e:
            report["issues"].append({"severity": "WARN", "kind": "STRUCTURE_CHECK", "msg": f"Structure check skipped: {e}"})

    return text, report


def needs_fix(original: str, cleaned: str, report: Dict[str, Any]) -> bool:
    """Fix if text changed OR parse not OK OR any ERROR present."""
    if original != cleaned:
        return True
    if not report.get("parse_ok", True):
        return True
    for it in report.get("issues", []):
        if it.get("severity") == "ERROR":
            return True
    return False


def backup_name_for(path: Path) -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.stem}__backup_{ts}.xml")


def resolve_patterns(args: argparse.Namespace) -> List[str]:
    if args.pattern:
        return args.pattern
    if args.only_problemset and args.only_mcq:
        return DEFAULT_PATTERNS
    if args.only_problemset:
        return ["*_problemset.xml"]
    if args.only_mcq:
        return ["*_problemset_mcq.xml"]
    return DEFAULT_PATTERNS


# ---------- Core runner ----------
def _process_files(patterns: List[str]) -> int:
    print("Scanning patterns:", ", ".join(patterns))

    files: List[Path] = []
    for pat in patterns:
        files.extend([Path(p) for p in glob.glob(pat)])
    files = sorted(set(f.resolve() for f in files))

    if not files:
        print("No matching XML files found.")
        return 0

    summary = {"checked": 0, "fixed": 0, "ok": 0, "errors_after_fix": 0}
    per_file_results = []

    for f in files:
        summary["checked"] += 1
        try:
            original = f.read_text(encoding="utf-8", errors="strict")
        except Exception as e:
            per_file_results.append((f.name, "ERROR", f"Cannot read file: {e}"))
            summary["errors_after_fix"] += 1
            continue

        cleaned, report = sanitize_text(original)
        must_fix = needs_fix(original, cleaned, report)

        if not must_fix:
            per_file_results.append((f.name, "OK", "No changes required"))
            summary["ok"] += 1
            continue

        # Write backup
        try:
            bak = backup_name_for(f)
            i = 1
            b = bak
            while b.exists():
                b = bak.with_name(bak.stem + f"_{i}" + bak.suffix)
                i += 1
            b.write_text(original, encoding="utf-8")
        except Exception as e:
            per_file_results.append((f.name, "ERROR", f"Failed to write backup: {e}"))
            summary["errors_after_fix"] += 1
            continue

        # Overwrite original with sanitized content
        try:
            f.write_text(cleaned, encoding="utf-8")
        except Exception as e:
            per_file_results.append((f.name, "ERROR", f"Failed to write sanitized file: {e}"))
            summary["errors_after_fix"] += 1
            continue

        if not report.get("parse_ok", True):
            target = f.with_name(f"{f.stem}__error.xml")
            i = 1
            while target.exists():
                target = f.with_name(f"{f.stem}__error_{i}.xml")
                i += 1
            try:
                f.rename(target)
                shown_name = target.name
            except Exception:
                shown_name = f.name
            per_file_results.append(
                (shown_name, "FIXED_WITH_ERRORS",
                 "Sanitized and saved under '__error' name, but XML still fails to parse — see details above")
            )
            summary["fixed"] += 1
            summary["errors_after_fix"] += 1
        else:
            errs = [it for it in report["issues"] if it["severity"] == "ERROR"]
            warns = [it for it in report["issues"] if it["severity"] == "WARN"]
            short = []
            if errs:
                short.append(f"errors={len(errs)}")
            if warns:
                short.append(f"warnings={len(warns)}")
            if report.get("unicode_replacements"):
                total_rep = sum(report["unicode_replacements"].values())
                short.append(f"unicode_replaced={total_rep}")
            if report.get("structural_fixes"):
                tot = sum(report["structural_fixes"].values())
                if tot:
                    short.append(f"structural_fixes={tot}")
            msg = "; ".join(short) if short else "Sanitized"
            per_file_results.append((f.name, "FIXED", msg))
            summary["fixed"] += 1

        print(f"\n=== {f.name} ===")
        for it in report["issues"]:
            print(f"- {it['severity']}: {it['kind']}: {it['msg']}")

    print("\n================ Summary ================")
    print(f"Checked : {summary['checked']} file(s)")
    print(f"OK      : {summary['ok']}")
    print(f"Fixed   : {summary['fixed']}")
    print(f"Errors  : {summary['errors_after_fix']}")
    print("=========================================")

    print("\nFile status:")
    for name, status, msg in per_file_results:
        print(f"- {name}: {status} — {msg}")

    return 0


# ---------- Public API ----------
def run(patterns: List[str] = None, *, only_problemset: bool = False, only_mcq: bool = False) -> int:
    if patterns:
        return _process_files(patterns)

    if only_problemset and only_mcq:
        pats = DEFAULT_PATTERNS
    elif only_problemset:
        pats = ["*_problemset.xml"]
    elif only_mcq:
        pats = ["*_problemset_mcq.xml"]
    else:
        pats = DEFAULT_PATTERNS
    return _process_files(pats)


def cli() -> int:
    ap = argparse.ArgumentParser(description="Sanitize Moodle Question Bank XML files in the current directory.")
    ap.add_argument("--only-problemset", action="store_true", help='Scan only "*_problemset.xml"')
    ap.add_argument("--only-mcq", action="store_true", help='Scan only "*_problemset_mcq.xml"')
    ap.add_argument("--pattern", action="append", default=[], help='Custom glob pattern(s). Repeatable. Overrides --only-* flags.')
    args = ap.parse_args()
    patterns = args.pattern if args.pattern else (["_problemset.xml","*_problemset_mcq.xml"] if (args.only_problemset and args.only_mcq) else (["*_problemset.xml"] if args.only_problemset else (["*_problemset_mcq.xml"] if args.only_mcq else ["*_problemset_mcq.xml","*_problemset.xml"])))
    return _process_files(patterns)


def main(*patterns: str) -> int:
    if patterns:
        return _process_files(list(patterns))
    return cli()


if __name__ == "__main__":
    sys.exit(cli())
