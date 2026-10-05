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

"""
sanitize_xml.py
Sanitize Moodle Question Bank XML files (CLI or programmatic).

Programmatic usage:
  import sanitize_xml
  sanitize_xml.main("*_problemset.xml")
  sanitize_xml.main("*_problemset.xml", "*_problemset_mcq.xml")
  sanitize_xml.run(only_problemset=True)

This version:
- Repairs missing <text> wrapper around CDATA for Moodle blocks (questiontext, feedback, etc.)
- Repairs broken CDATA openers like [CDATA[ → <![CDATA[
- Removes XML 1.0–invalid control characters
- Normalizes risky Unicode typography to ASCII-safe
- Escapes stray '&' outside valid entities and outside CDATA
- Parses once; if ok, normalizes misspelled <question type="..."> values (e.g., multichoichoice)
- Re-serializes ONLY when the XML tree is changed (to avoid unnecessary CDATA loss)
- Provides both CLI and programmatic entry points
"""

import sys
import re
import time
import glob
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any
import xml.etree.ElementTree as ET

# ---------- Defaults ----------
DEFAULT_PATTERNS = ["*_problemset_mcq.xml", "*_problemset.xml"]

# Normalize common question-type typos that Moodle rejects
TYPE_TYPO_MAP = {
    "multichoichoice": "multichoice",
    "multichoise": "multichoice",
    "multihoice": "multichoice",
    # add more if you encounter them
}

# Replace risky unicode that often breaks strict Moodle importers
# Replace risky unicode that often breaks strict Moodle importers

RISKY_REPLACEMENTS = {
    # =========================================================
    # 1. KEEP THESE ACTIVE (Uncommented)
    # These are invisible characters that often cause bugs.
    # We want to strip them (replace with empty string "").
    # =========================================================
    
    # --- zero-width / BOM / joiners (remove) ---
    "\u200B": "", "\u200C": "", "\u200D": "", "\ufeff": "", "\u2060": "",

    # --- bidi/formatting marks (remove) ---
    "\u200E": "", "\u200F": "", "\u202A": "", "\u202B": "", "\u202C": "",
    "\u202D": "", "\u202E": "", "\u2066": "", "\u2067": "", "\u2068": "", "\u2069": "",


    # =========================================================
    # 2. COMMENT OUT EVERYTHING BELOW HERE
    # We want to PRESERVE all these symbols for the physics display.
    # =========================================================

    # # --- hyphens/dashes/minus (normalize to '-') ---
    # "\u00AD": "-", "\u2010": "-", "\u2011": "-", "\u2012": "-", 
    # "\u2013": "-", "\u2014": "-", "\u2015": "-", "\u2212": "-",

    # # --- spaces (normalize to plain space) ---
    # "\u00A0": " ", "\u2000": " ", "\u2001": " ", "\u2002": " ", ...

    # # --- quotes/apostrophes ---
    # "\u2018": "'", "\u2019": "'", "\u201C": '"', "\u201D": '"', ...

    # # --- bullets / dot-like / ellipses ---
    # "\u2022": "-", "\u2043": "-", "\u00B7": ".", "\u2026": "...", 

    # # --- math operators / relations ---
    # "\u00D7": "x", "\u00F7": "/", "\u00B1": "+/-", "\u2264": "<=", 
    # "\u2265": ">=", "\u2260": "!=", "\u2248": "~", "\u221A": "sqrt", 
    # "\u221E": "infinity", "\u2192": "->", "\u2190": "<-", ...

    # # --- degrees / temperature ---
    # "\u00B0": " degrees ", "\u2103": " degC ", "\u2109": " degF ",

    # # --- Greek letters ---
    # "\u03B1": "alpha", "\u03B2": "beta", ... (and all others)

    # # --- misc technical symbols ---
    # "\u2126": "ohm", "\u212A": "K", "\u00B5": "u", ...

    # # --- superscripts/subscripts ---
    # "\u2070": "^0", "\u00B9": "^1", ...
}

# Disallowed XML 1.0 control characters (except TAB, LF, CR)
CTRL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
# Valid entity pattern for &…; detection
VALID_ENTITY = re.compile(r"&(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9A-Fa-f]+);")

# ---------- Pre-salvage for defective files ----------
NOISE_PATTERNS = [
    r"^\s*```.*?$",           # markdown code fence start
    r"^\s*```\s*$",           # markdown code fence end
    r"^\s*<<<\s*BEGIN_QUIZ_XML\s*>>>.*?$",
    r"^\s*<<<\s*END_QUIZ_XML\s*>>>.*?$",
    r"^\s*BEGIN_QUIZ_XML\s*$",
    r"^\s*END_QUIZ_XML\s*$",
    r"^\s*Here is the XML.*?$",
    r"^\s*<\?xml[^>]*>\s*$",  # stray XML declarations as standalone lines
]
NOISE_REGEXES = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in NOISE_PATTERNS]

def strip_non_xml_noise(text: str) -> str:
    # Remove BOM first (if any)
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    # Remove common noise lines
    for rgx in NOISE_REGEXES:
        text = rgx.sub("", text)
    # Drop any prose before the first '<'
    first_lt = text.find("<")
    if first_lt > 0:
        text = text[first_lt:]
    # Trim trailing junk after the last '>'
    last_gt = text.rfind(">")
    if last_gt != -1 and last_gt + 1 < len(text):
        text = text[:last_gt + 1]
    return text.strip()

def extract_or_wrap_quiz(text: str) -> str:
    """
    Prefer the first <quiz>...</quiz> block. If none exists but <question> blocks
    are present, wrap them in a synthetic <quiz> root.
    """
    m = re.search(r"<quiz\b.*?</quiz>", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(0).strip()
    qs = re.findall(r"<question\b.*?</question>", text, flags=re.DOTALL | re.IGNORECASE)
    if qs:
        inner = "\n".join(qs)
        return f"<quiz>\n{inner}\n</quiz>"
    return text.strip()

def fix_unclosed_cdata(text: str) -> str:
    # Normalize slightly malformed CDATA open/close spacing
    text = re.sub(r"<!\s*\[CDATA\[", "<![CDATA[", text)
    text = re.sub(r"\]\]\s*>", "]]>", text)
    # Count openings and closings
    opens = len(re.findall(r"<!\[CDATA\[", text))
    closes = len(re.findall(r"\]\]>", text))
    if opens > closes:
        text = text + ("]]>" * (opens - closes))
    return text



# ---------- Helpers ----------
def find_cdata_regions(text: str) -> List[Tuple[int, int]]:
    """Return [ (start,end) ] index spans of CDATA sections."""
    regions = []
    start = 0
    while True:
        s = text.find("<![CDATA[", start)
        if s == -1:
            break
        e = text.find("]]>", s)
        if e == -1:
            regions.append((s, len(text)))  # unclosed CDATA to end-of-text
            break
        regions.append((s, e + 3))
        start = e + 3
    return regions


def indexes_outside_regions(text: str, pattern: re.Pattern, regions: List[Tuple[int, int]]) -> List[int]:
    """Return start indices of matches that are not inside any region span."""
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
    """
    Fix cases like:
      <tag ...><![CDATA[...]]></text></tag>
      <tag ...><![CDATA[...]]></tag>
    by wrapping CDATA in a proper <text> child:
      <tag ...><text><![CDATA[...]]></text></tag>
    """
    count = 0

    # Case A: explicit stray </text> after CDATA
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

    # Case B: CDATA directly inside tag (no <text>)
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
    """
    Normalize all Moodle blocks that must contain a <text> child.
    This covers the common mismatch causing early parse errors.
    """
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
    """Fix misspelled <question type="..."> values and trim/case-normalize."""
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
            # Clean stray spaces / inconsistent case
            q.set("type", t_lower)
            fixes += 1
    if fixes:
        report["issues"].append({
            "severity": "WARN",
            "kind": "QUESTION_TYPE_TYPO",
            "msg": f"Normalized/fixed {fixes} question type value(s) (e.g., multichoichoice→multichoice).",
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
      - Risky unicode normalized to ASCII
      - Stray & escaped (outside CDATA / not an entity)
      - BOM stripped
      - XML parsing verified
      - Light Moodle checks; normalize question type typos
    """
    report: Dict[str, Any] = {
        "issues": [],
        "unicode_replacements": {},
        "changed": False,
        "structural_fixes": {}
    }

    # 0) PRE-SALVAGE: strip obvious non-XML noise, keep only the main <quiz> block (or wrap <question> blocks),
    # and balance/normalize CDATA markers
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

    # 1) STRUCTURAL: wrap CDATA in <text> where missing (pre-parse)
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

    # 2) Repair broken CDATA opener like <text>[CDATA[ ... ]]> → <text><![CDATA[ ... ]]>
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
    open_count = text.count("<![CDATA[")  # correct open token
    close_count = text.count("]]>")
    if open_count != close_count:
        report["issues"].append({
            "severity": "ERROR",
            "kind": "CDATA_BALANCE",
            "msg": f"Unbalanced CDATA sections: openings={open_count}, closings={close_count}."
        })

    # 5) Remove XML 1.0 control characters
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

    # 6) Replace risky Unicode typography
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

    # 7) Escape stray '&' outside CDATA (and outside known entities)
    regions = find_cdata_regions(text)
    amp_positions = indexes_outside_regions(text, re.compile(r"&"), regions)
    stray_positions = []
    for pos in amp_positions:
        segment = text[pos:pos + 24]  # quick lookahead window
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

    # 8) Parse once, then semantic fixes / checks
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

        # Normalize misspelled/odd-cased question type values
        if normalize_question_types(root, report):
            tree_changed = True

        # Re-serialize only if tree_changed
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
    """Backup name that will NOT match the scan patterns."""
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


# ---------- Core runner (shared by CLI & programmatic) ----------
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

        # Write backup (guaranteed not to match the target patterns)
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
            #per_file_results.append((f.name, "FIXED_WITH_ERRORS",
            #                         "Sanitized and saved, but XML still fails to parse — see details above"))
            #summary["fixed"] += 1
            #summary["errors_after_fix"] += 1
            #
            # Rename sanitized file to *__error.xml
            target = f.with_name(f"{f.stem}__error.xml")
            i = 1
            while target.exists():
                target = f.with_name(f"{f.stem}__error_{i}.xml")
                i += 1
            try:
                f.rename(target)
                shown_name = target.name
            except Exception:
                shown_name = f.name  # fallback if rename fails

            per_file_results.append(
                (shown_name, "FIXED_WITH_ERRORS",
                 "Sanitized and saved under '__error' name, but XML still fails to parse — see details above")
            )
            summary["fixed"] += 1
            summary["errors_after_fix"] += 1
            #
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

        # Detailed issues for changed files
        print(f"\n=== {f.name} ===")
        for it in report["issues"]:
            print(f"- {it['severity']}: {it['kind']}: {it['msg']}")

    # Final report
    print("\n================ Summary ================")
    print(f"Checked : {summary['checked']} file(s)")
    print(f"OK      : {summary['ok']}")
    print(f"Fixed   : {summary['fixed']}")
    print(f"Errors  : {summary['errors_after_fix']} (remaining parse errors or IO problems)")
    print("=========================================")

    print("\nFile status:")
    for name, status, msg in per_file_results:
        print(f"- {name}: {status} — {msg}")

    return 0


# ---------- Public API ----------
def run(patterns: List[str] = None, *, only_problemset: bool = False, only_mcq: bool = False) -> int:
    """
    Programmatic flags-style API.
    - If 'patterns' is provided, it overrides the flags.
    - Otherwise, choose based on flags (or both by default).
    """
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
    """CLI entry point."""
    ap = argparse.ArgumentParser(description="Sanitize Moodle Question Bank XML files in the current directory.")
    ap.add_argument("--only-problemset", action="store_true", help='Scan only "*_problemset.xml"')
    ap.add_argument("--only-mcq", action="store_true", help='Scan only "*_problemset_mcq.xml"')
    ap.add_argument("--pattern", action="append", default=[], help='Custom glob pattern(s). Repeatable. Overrides --only-* flags.')
    args = ap.parse_args()
    patterns = resolve_patterns(args)
    return _process_files(patterns)


def main(*patterns: str) -> int:
    """
    Programmatic convenience:
      main("*_problemset.xml")
      main("*_problemset.xml", "*_problemset_mcq.xml")
    If no patterns are passed, it falls back to CLI (argv parsing).
    """
    if patterns:
        return _process_files(list(patterns))
    return cli()


if __name__ == "__main__":
    sys.exit(cli())
