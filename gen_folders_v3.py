#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re, shutil, json, csv
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter

# === INPUTS ===
pdf_path  = "source.pdf"                      # full book PDF
json_path = "subchapter_index_physical.json"  # index produced earlier
output_dir = "."                              # where to emit PDFs

os.makedirs(output_dir, exist_ok=True)

# === LOAD INDEX ===
with open(json_path, "r", encoding="utf-8") as f:
    subchapters = json.load(f)

# === LOAD PDF ===
reader = PdfReader(pdf_path)
n_pages = len(reader.pages)

def clean_filename(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = s.replace("’", "").replace("'", "")
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"

def chapter_of_title(title: str) -> str | None:
    """Return the leading chapter digits from a title like '4.6 ...' or '4 ...' """
    m = re.match(r"^\s*(\d+)(?:\.(\d+))?", title)
    return m.group(1) if m else None

made = 0
skipped = 0

# === 1) EXTRACT EACH RANGE TO PDF WITH ROBUST NAMING ===
for entry in subchapters:
    title = entry.get("title", "").strip()
    bphys = entry.get("begin_physical")
    ephys = entry.get("end_physical")

    # Skip incomplete ranges (e.g., Chapter 17 entries that are null in your JSON)
    if bphys is None or ephys is None:
        skipped += 1
        print(f"⚠️ Skipping '{title}' because begin/end_physical is null.")
        continue

    # 0-based inclusive indices
    start = bphys - 1
    end   = ephys - 1
    if start < 0 or start >= n_pages:
        print(f"⚠️ Skipping '{title}' due to start={start} out of bounds (pdf has {n_pages} pages).")
        skipped += 1
        continue
    end = min(end, n_pages - 1)
    if end < start:
        print(f"⚠️ Skipping '{title}' due to end < start after bounds clamp.")
        skipped += 1
        continue

    # Decide filename
    chap = chapter_of_title(title)
    numbered = re.match(r"^\s*(\d+)\.(\d+)", title)

    if numbered:
        major, minor = numbered.groups()
        filename = f"{major}-{minor}.pdf"
    else:
        # Unnumbered sections → stable, chapter-prefixed names to prevent overwrite
        t = title.lower()
        if "questions to guide your review" in t:
            filename = f"{chap}-questions-to-guide-your-review.pdf" if chap else f"chx-questions-to-guide-your-review.pdf"
        elif "practice exercises" in t:
            filename = f"{chap}-practice-exercises.pdf" if chap else f"chx-practice-exercises.pdf"
        elif "additional and advanced exercises" in t:
            filename = f"{chap}-additional-and-advanced-exercises.pdf" if chap else f"chx-additional-and-advanced-exercises.pdf"
        elif any(k in t for k in ["problem set", "problems"]):
            filename = f"{chap}-problems.pdf" if chap else "chx-problems.pdf"
        else:
            slug = clean_filename(title)
            filename = f"{chap}-{slug}.pdf" if chap else f"chx-{slug}.pdf"

    # Write the slice
    writer = PdfWriter()
    for i in range(start, end + 1):
        writer.add_page(reader.pages[i])
    with open(os.path.join(output_dir, filename), "wb") as f:
        writer.write(f)
    made += 1
    print(f"✅ Saved: {filename}")

print(f"— Completed extraction: {made} files, {skipped} skipped due to nulls or bounds.")

# === 2) MOVE chapter-subchapter PDFs INTO CHAPTER FOLDERS ===
for filename in list(os.listdir(output_dir)):
    if not filename.endswith(".pdf"):
        continue
    m = re.match(r"^(\d+)[\-.]", filename)  # pick up leading chapter number
    if not m:
        # no chapter number — leave in place
        continue
    chapter = m.group(1)
    os.makedirs(chapter, exist_ok=True)
    src = os.path.join(output_dir, filename)
    dst = os.path.join(chapter, filename)
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.move(src, dst)
        print(f"Moved {filename} → {chapter}/")

# === Helper: compute “last subchapter” per chapter (for problems placement) ===
def get_last_subchapters_from_index(data):
    last = {}
    for e in data:
        t = e.get("title", "")
        m = re.match(r"^\s*(\d+)\.(\d+)", t)
        if m:
            chap = m.group(1)
            sub  = f"{m.group(1)}.{m.group(2)}"
            last[chap] = sub
    # return sorted by chapter
    return [ last[k] for k in sorted(last.keys(), key=lambda x: int(x)) ]

lastsubchaplist = get_last_subchapters_from_index(subchapters)
lastsubchapdirs = [ Path(os.path.join(s.split('.')[0], s)) for s in lastsubchaplist ]
lastsubchapdirs_str = [p.name for p in lastsubchapdirs]
print("lastsubchapdirs_str are", lastsubchapdirs_str, "\n")

# === 3) MOVE each chapter’s PDFs into subchapter or problems folders and stage files ===
root_dir = "."
origdir = os.getcwd()

for chapter in os.listdir(root_dir):
    chapter_path = os.path.join(root_dir, chapter)
    if not os.path.isdir(chapter_path) or not chapter.isdigit():
        continue

    for filename in os.listdir(chapter_path):
        if not filename.endswith(".pdf"):
            continue

        file_path = os.path.join(chapter_path, filename)
        sub_match  = re.match(r"^(\d+)-(\d+)\.pdf$", filename)
        qgr_match  = re.match(r"^(\d+)-questions-to-guide-your-review\.pdf$", filename)
        prac_match = re.match(r"^(\d+)-practice-exercises\.pdf$", filename)
        adv_match  = re.match(r"^(\d+)-additional-and-advanced-exercises\.pdf$", filename)
        prob_match = re.match(r"^(\d+)-problems\.pdf$", filename)

        dest_dir = None
        sub_id   = None

        if sub_match:
            major, minor = sub_match.groups()
            sub_id = f"{major}.{minor}"
            dest_dir = os.path.join(chapter_path, sub_id)
        elif prob_match:
            major = prob_match.group(1)
            sub_id = f"{major}.problems"
            dest_dir = os.path.join(chapter_path, "problems")
        elif qgr_match:
            major = qgr_match.group(1)
            sub_id = f"{major}.qgr"
            dest_dir = os.path.join(chapter_path, "qgr")
        elif prac_match:
            major = prac_match.group(1)
            sub_id = f"{major}.practice"
            dest_dir = os.path.join(chapter_path, "practice-exercises")
        elif adv_match:
            major = adv_match.group(1)
            sub_id = f"{major}.advanced"
            dest_dir = os.path.join(chapter_path, "additional-and-advanced-exercises")
        else:
            print(f"⚠️ Skipping unrecognized file: {filename}")
            continue

        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, "source_orig.pdf")
        shutil.move(file_path, dest_path)
        print(f"✅ Moved {filename} → {dest_path}")

        # Copy all helper files from {origdir} except the heavy book PDF
        for p in os.listdir(origdir):
            if os.path.isfile(p) and p != 'source.pdf':
                shutil.copy(p, dest_dir)
        print(f"All helper files from {origdir} copied to {dest_dir}")

        # If this is one of the *last* subchapters, also mirror into problems/
        if sub_id and sub_id.split('.')[0] in [s.split('.')[0] for s in lastsubchapdirs_str] and sub_id in lastsubchapdirs_str:
            # already handled by list above; nothing special needed here
            pass

# === 4) Build subchapters.csv (chapter, subchapter, full_path) ===
csv_path = Path("subchapters.csv")
print(f"To create {csv_path}")
base_path = Path(".")
pattern = re.compile(r"^\d+$")
rows = []
for path in base_path.iterdir():
    if path.is_dir() and pattern.match(path.name):
        for path2 in path.iterdir():
            if path2.is_dir():
                rows.append([path2.parent.name, path2.name, str(path2.resolve())])

with csv_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["chapter", "subchapter", "full_path"])
    for row in rows:
        w.writerow(row)
print(f"Saved {len(rows)} rows to {csv_path}")


# === 5) Cleanup: remove any chx-*.pdf in . and all subdirectories ===
from pathlib import Path

removed = 0
errors_remove = 0
for p in Path(".").rglob("chx-*.pdf"):
    try:
        p.unlink()
        removed += 1
        print(f"🗑️  Removed: {p}")
    except Exception as e:
        errors_remove += 1
        print(f"⚠️  Failed to remove {p}: {e}")

print(f"Cleanup complete: removed {removed} file(s); {errors_remove} error(s).")

# === 6) Rename every source_orig.pdf → source.pdf in all subdirectories ===
renamed = 0
skipped = 0
errors_rename = 0
for src in Path(".").rglob("source_orig.pdf"):
    dst = src.with_name("source.pdf")
    try:
        # Overwrite if destination already exists
        if dst.exists():
            # If you prefer to skip instead of overwrite, comment the next line and uncomment the two lines after.
            dst.unlink()
            # print(f"⚠️  Skip rename (exists): {dst}"); skipped += 1; continue

        src.replace(dst)  # atomic-ish rename; overwrites if we unlinked above
        renamed += 1
        print(f"✏️  Renamed: {src} → {dst}")
    except Exception as e:
        errors_rename += 1
        print(f"⚠️  Failed to rename {src}: {e}")

print(f"Rename complete: {renamed} renamed; {skipped} skipped; {errors_rename} error(s).")
