#!/usr/bin/env python3
"""Build an offline reviewer package from an already verified MicroGen lecture.

Read-only source, no external calls, no academic approval. Copies reference
source, video, per-slide audio, and previews to an independent review folder.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import tempfile
import wave
from pathlib import Path
import microgen_quality as quality


class ReviewPackError(RuntimeError):
    pass


def esc(value):
    return html.escape(str(value), quote=True)


def clock(seconds):
    n = int(seconds)
    return f"{n//3600:02d}:{n//60%60:02d}:{n%60:02d}"


def source_page_number(crop, source_page_count):
    """Return a 1-based textbook page only when a receipt reference is unambiguous."""
    if not isinstance(crop, dict):
        return None
    raw = crop.get("source_page", crop.get("page"))
    if type(raw) is int:
        number = raw
    elif isinstance(raw, str):
        match = re.fullmatch(r"(?:page[_\s-]*)?([0-9]+)", raw.strip(), flags=re.I)
        number = int(match.group(1)) if match else None
    else:
        return None
    return number if number is not None and 1 <= number <= source_page_count else None


def render_unmapped_crops(crops, source_page_count):
    """Show traceable *whole-page* previews; never claim to reproduce a lost crop."""
    if not crops:
        return "<li>None recorded</li>"
    rows = []
    for idx, crop in enumerate(crops, 1):
        record = crop if isinstance(crop, dict) else {"note": crop}
        label = record.get("filename") or record.get("name") or f"Crop {idx}"
        page = source_page_number(record, source_page_count)
        location = (
            f'<a href="#source-page-{page:03d}">Inspect source page {page}</a>'
            if page is not None
            else "Source page unresolved; inspect the textbook manually"
        )
        note = record.get("note")
        note_html = f" — {esc(note)}" if note else ""
        rows.append(
            f"<li><strong>{esc(label)}</strong>: {location}{note_html}. "
            "This link opens the whole textbook page, not an extracted crop.</li>"
        )
    return "".join(rows)


def thumbnails(pdf, destination, prefix):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    result = []
    with fitz.open(pdf) as doc:
        if not doc.page_count:
            raise ReviewPackError("Empty PDF")
        for i, page in enumerate(doc, 1):
            zoom = min(1.5, 800 / max(float(page.rect.width), 1.0))
            filename = f"{prefix}_{i:03d}.png"
            page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).save(
                destination / filename
            )
            result.append("previews/" + filename)
    return result


def duration(wav):
    with wave.open(str(wav), "rb") as obj:
        if obj.getframerate() <= 0 or obj.getnframes() <= 0:
            raise ReviewPackError("Empty audio file")
        return obj.getnframes() / obj.getframerate()


def build_pack(source, output, *, edition="published"):
    source = Path(source).resolve()
    output = Path(output).resolve()
    if not quality.published_manifest_valid(source):
        raise ReviewPackError("Source media bundle has no valid completion receipt")
    if source == output or source in output.parents:
        raise ReviewPackError("Review pack must not be written inside source")
    if output.exists():
        raise ReviewPackError("Existing review folder is protected: " + str(output))
    old_receipt = (source / ".microgen_verified_completion.json").read_bytes()
    approved_hash = hashlib.sha256(old_receipt).hexdigest()
    receipt = json.loads(old_receipt)
    slides = receipt["slide_count"]
    sidecar = json.loads((source / "script_tts.json").read_text(encoding="utf-8"))
    entries = sidecar["slides"]
    if [item["slide"] for item in entries] != list(range(1, slides+1)):
        raise ReviewPackError("Narration slide numbers not consecutive")
    if len(receipt["wav_sha256"]) != slides:
        raise ReviewPackError("WAV checksum count mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".microgen_review_", dir=output.parent))
    try:
        (stage / "previews").mkdir()
        (stage / "media").mkdir()
        pictures = thumbnails(source / "slides.pdf", stage / "previews", "slide")
        original = thumbnails(source / "source.pdf", stage / "previews", "source")
        if len(pictures) != slides:
            raise ReviewPackError("Slide count drift")
        for filename in ("slides.mp4", "source.pdf", "slides.pdf"):
            shutil.copy2(source / filename, stage / "media" / filename)
            if quality.sha256(stage / "media" / filename) != quality.sha256(source / filename):
                raise ReviewPackError("Media changed in transit: "+filename)
        data = []
        start = 0.
        for idx, entry in enumerate(entries, 1):
            file = f"slide{idx}.wav"
            copied = stage / "media" / file
            shutil.copy2(source / file, copied)
            if quality.sha256(copied) != receipt["wav_sha256"][idx-1]:
                raise ReviewPackError("WAV checksum mismatch: "+file)
            length = duration(copied)
            data.append({
                "slide": idx, "title": entry.get("title") or f"Slide {idx}",
                "start_seconds": round(start, 3), "duration_seconds": round(length, 3),
                "narration": entry.get("narration", ""), "tts_text": entry.get("tts_text", ""),
                "image": pictures[idx-1], "audio": "media/"+file,
            })
            start += length
        if abs(start - receipt["audio_seconds"]) > 1.5:
            raise ReviewPackError("Narration WAV durations do not match receipt")
        info = {
            "schema_version": 1, "approval": "NOT_REVIEWED",
            "edition": edition, "section": source.name,
            "slides": data, "source_pages": original,
            "source_sha256": receipt["source_sha256"],
            "mp4_sha256": receipt["mp4_sha256"],
            "receipt_sha256": approved_hash,
            "source_page_count": len(original),
            "video_seconds": receipt["video_seconds"],
            "wav_seconds": round(start,3),
            "figure_display_warnings": receipt.get("figure_display_warnings", []),
            "unmapped_source_crops": receipt.get("unmapped_source_crops", []),
        }
        (stage / "review_inventory.json").write_text(
            json.dumps(info, indent=2, ensure_ascii=False)+"\n", encoding="utf-8"
        )
        rows = []
        cards = []
        for entry in data:
            n = entry["slide"]
            rows.append(f"| {n} | {clock(entry['start_seconds'])} | "
                        f"{str(entry['title']).replace('|','/')} | [ ] | [ ] | [ ] | [ ] |")
            extra = ""
            if entry["tts_text"] != entry["narration"]:
                extra = ("<details><summary>Separate TTS pronunciation text</summary><p>"
                         + esc(entry["tts_text"]) + "</p></details>")
            cards.append(
                f"<article id='slide-{n}'><h3>Slide {n}: {esc(entry['title'])}</h3>"
                f"<small>Start {clock(entry['start_seconds'])}; audio {entry['duration_seconds']:.1f} s</small> "
                f"<button onclick='jump({entry['start_seconds']})'>Play from here</button>"
                f"<img src='{esc(entry['image'])}' alt='Slide {n}' loading='lazy'>"
                f"<p>{esc(entry['narration'])}</p>{extra}"
                f"<audio controls preload='none' src='{esc(entry['audio'])}'></audio>"
                f"<fieldset><legend>Manual review</legend>"
                + "".join(
                    f"<label><input class='review' type='checkbox' data-slide='{n}' data-kind='{field}'>"
                    + label + "</label>"
                    for field,label in [("math","Mathematics"),("figures","Figures"),
                                        ("narration","Narration"),("audio","Audio")]
                )
                + f"<textarea data-slide='{n}' placeholder='Corrections, source citations or comments'></textarea>"
                + "</fieldset></article>"
            )
        checklist = (
            f"# Lecturer review checklist: Section {source.name}\n\n"
            "**NOT REVIEWED. This file is a handoff, not an approval.**\n\n"
            f"Source SHA256: {info['source_sha256']}\n\n"
            f"MP4 SHA256: {info['mp4_sha256']}\n\n"
            "| Slide | Video time | Title | Mathematics | Figures | Narration | Audio |\n"
            "|---:|---|---|:---:|:---:|:---:|:---:|\n"
            + "\n".join(rows)
            + "\n\n## Final decisions\n\n"
            "- [ ] Every needed mathematical statement reviewed\n"
            "- [ ] Complete source figure panels checked\n"
            "- [ ] Video listened to with audio pronunciation and timing checked\n"
            "- [ ] Longer-than-ten-minute lesson policy checked if applicable\n"
            "- [ ] Lecturer release approval provided separately\n\nNotes:\n"
        )
        if info["unmapped_source_crops"]:
            checklist += (
                "\n## Unmapped textbook crop classification (human review required)\n\n"
                "The link in index.html opens the entire source page, not the missing crop.\n"
                "For each entry determine whether a teaching figure is omitted; do not assume it is.\n\n"
            )
            for idx, item in enumerate(info["unmapped_source_crops"], 1):
                record = item if isinstance(item, dict) else {"note": item}
                raw_label = record.get("filename") or record.get("name") or f"Crop {idx}"
                safe_label = str(raw_label).replace("|", "/").replace("`", "'").replace("[", "(").replace("]", ")").replace("\r", " ").replace("\n", " ")[:120]
                page_number = source_page_number(record, len(original))
                where = f"source page {page_number}" if page_number else "source page unresolved"
                checklist += (
                    f"- [ ] Crop {idx}, {safe_label} ({where}): "
                    "classify as required / not needed / uncertain, record explanation.\n"
                )
        (stage / "REVIEW_CHECKLIST.md").write_text(checklist, encoding="utf-8")
        refs = "".join(
            f"<figure id='source-page-{idx:03d}'>"
            f"<img src='{esc(path)}' alt='Source page {idx}' loading='lazy'>"
            f"<figcaption>Source page {idx}</figcaption></figure>"
            for idx,path in enumerate(original,1)
        )
        warnings = "".join(
            f"<li>Slide {esc(item.get('slide','?'))}, display width "
            f"{esc(item.get('display_width_fraction','?'))} of slide</li>"
            for item in info["figure_display_warnings"]
        ) or "<li>None recorded</li>"
        unmapped = render_unmapped_crops(
            info["unmapped_source_crops"], len(original)
        )
        duration_warning = (
            "<p class='warning'>This MP4 exceeds ten minutes. Confirm whether "
            "a per-video limit applies to this course before publishing.</p>"
            if receipt["video_seconds"] >= 600 else ""
        )
        javascript = """
const info = INFOJSON;
const storageKey='microgen-review-'+info.source_sha256+'-'+info.mp4_sha256;
function jump(t){const video=document.getElementById('video');video.currentTime=t;video.play().catch(()=>{});video.scrollIntoView({block:'center',behavior:'smooth'});}
function snapshot(){const result={schema_version:1,status:'DRAFT_UNAPPROVED',source_sha256:info.source_sha256,mp4_sha256:info.mp4_sha256,slides:{}};document.querySelectorAll('article').forEach(el=>{const n=el.id.split('-')[1];const checks={};el.querySelectorAll('input.review').forEach(box=>checks[box.dataset.kind]=box.checked);result.slides[n]={checks,notes:el.querySelector('textarea').value};});return result;}
function restore(data){if(data.source_sha256!==info.source_sha256||data.mp4_sha256!==info.mp4_sha256){alert('Review was made for a different media version.');return;}Object.entries(data.slides||{}).forEach(([n,s])=>{const el=document.getElementById('slide-'+n);if(!el)return;el.querySelectorAll('input.review').forEach(box=>box.checked=!!(s.checks||{})[box.dataset.kind]);el.querySelector('textarea').value=s.notes||'';});}
function persist(){try{localStorage.setItem(storageKey,JSON.stringify(snapshot()));}catch(e){}}
function save(){const blob=new Blob([JSON.stringify(snapshot(),null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='review_'+info.section.replace('.','_')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
function load(el){const f=el.files&&el.files[0];if(!f)return;f.text().then(x=>{try{restore(JSON.parse(x));persist();}catch(e){alert(e.message)}});el.value='';}
try{const x=localStorage.getItem(storageKey);if(x)restore(JSON.parse(x));}catch(e){}
document.querySelectorAll('input.review,textarea').forEach(el=>{el.addEventListener('change',persist);el.addEventListener('input',persist)});
"""
        safe_data = json.dumps({k:info[k] for k in ("section","source_sha256","mp4_sha256")}).replace("<","\\u003c")
        javascript = javascript.replace("INFOJSON",safe_data)
        page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MicroGen Review: {esc(source.name)}</title>
<style>
body{{font:16px/1.5 system-ui,Arial,sans-serif;max-width:1100px;margin:auto;padding:20px;background:#f4f6f9;color:#193047}}
h1,h2,h3{{color:#173c5e}} article,header,figure{{background:white;border:1px solid #ccd5de;border-radius:6px;padding:15px;margin:14px 0}}
article img{{max-width:800px;width:100%;height:auto;display:block;margin:12px auto}}
article p{{white-space:pre-wrap}}video{{width:100%;max-height:460px;background:#111}}audio{{width:min(100%,550px)}}
button{{padding:8px 12px;background:#17577e;color:white;border:0;border-radius:5px;cursor:pointer}}
label{{display:inline-block;margin:7px}}textarea{{display:block;width:95%;min-height:70px;margin:8px}}
#sources{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}}
#sources img{{max-width:100%}}#sources figure:target{{outline:3px solid #17577e;scroll-margin-top:20px}}
.warning{{padding:12px;background:#ffedc5}}.muted{{color:#596d7d}}
</style></head><body><header><h1>Section {esc(source.name)} lecturer review</h1>
<strong>NOT REVIEWED — no academic or audio approval is implied.</strong>
<p>Edition: {esc(edition)}; slides: {slides}; textbook pages: {len(original)};
MP4 duration: {clock(receipt['video_seconds'])}</p>
<p class="muted">This private offline pack contains video, each slide's narration WAV,
PDF reference pages, and a checklist. Notes remain in the browser unless exported.
Exported notes do not certify student release.</p></header>{duration_warning}
<h2>Video playback</h2><video controls id="video" preload="metadata" src="media/slides.mp4"></video>
<p><button onclick="save()">Export review JSON</button>
<label>Import review JSON <input type="file" accept=".json" onchange="load(this)"></label></p>
<p><a href="REVIEW_CHECKLIST.md">Markdown checklist</a> ·
<a href="review_inventory.json">Bound review inventory</a> ·
<a href="media/source.pdf">Textbook source PDF</a></p>
<h2>Figure warnings</h2><ul>{warnings}</ul>
<h3>Unmapped source illustrations for classification</h3><ul>{unmapped}</ul>
<h2>Slide images, script and audio</h2>{''.join(cards)}
<h2>Textbook source pages</h2><div id="sources">{refs}</div>
<script>{javascript}</script></body></html>"""
        (stage / "index.html").write_text(page,encoding="utf-8")
        filehash = {
            x.relative_to(stage).as_posix():quality.sha256(x)
            for x in sorted(stage.rglob("*")) if x.is_file()
        }
        (stage / "review_pack_manifest.json").write_text(json.dumps({
            "schema_version":1,"approval":"NOT_REVIEWED",
            "source_receipt_sha256":approved_hash,"source_sha256":receipt["source_sha256"],
            "mp4_sha256":receipt["mp4_sha256"],"files_sha256":filehash,
        },indent=2,sort_keys=True)+"\n",encoding="utf-8")
        if (not quality.published_manifest_valid(source)
                or hashlib.sha256((source/".microgen_verified_completion.json").read_bytes()).hexdigest()!=approved_hash):
            raise ReviewPackError("Source changed during review-pack generation")
        os.replace(stage,output)
        return {"folder":str(output),"slides":slides,"source_pages":len(original),
                "files":len(filehash),"status":"NOT_REVIEWED","edition":edition}
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True)
        raise


def verify_pack(directory):
    """Independent, portable integrity check; does not certify academic QA."""
    root = Path(directory).resolve()
    try:
        manifest = json.loads((root/"review_pack_manifest.json").read_text(encoding="utf-8"))
        info = json.loads((root/"review_inventory.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ReviewPackError("Missing or unreadable review pack metadata") from exc
    if (manifest.get("schema_version") != 1 or manifest.get("approval") != "NOT_REVIEWED"
            or info.get("approval") != "NOT_REVIEWED"):
        raise ReviewPackError("Unexpected review pack schema or approval marker")
    files = manifest.get("files_sha256")
    if not isinstance(files, dict) or not files:
        raise ReviewPackError("No file hashes in reviewer package")
    for relative, digest in files.items():
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise ReviewPackError("Invalid review file hash entry")
        entry = Path(relative)
        full = (root/entry).resolve()
        if (entry.is_absolute() or ".." in entry.parts or not full.is_relative_to(root)
                or not full.is_file()):
            raise ReviewPackError(f"Missing or unsafe reviewer asset: {relative}")
        if quality.sha256(full) != digest:
            raise ReviewPackError(f"Reviewer asset checksum differs: {relative}")
    for filename, key in (("media/source.pdf","source_sha256"),
                          ("media/slides.mp4","mp4_sha256")):
        if quality.sha256(root/filename) != manifest.get(key):
            raise ReviewPackError(f"Lecture provenance hash mismatch: {filename}")
        if manifest[key] != info.get(key):
            raise ReviewPackError("Inventory and pack manifest hashes disagree")
    if len(info.get("slides",[])) != info.get("slide_count",len(info.get("slides",[]))):
        raise ReviewPackError("Review slide inventory differs from slide count")
    return {"directory":str(root),"integrity":"PASS","files":len(files),
            "slides":len(info["slides"]),"approval":"NOT_REVIEWED"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--verify",type=Path,help="Validate an existing reviewer package")
    parser.add_argument("--edition",choices=["published","qa-candidate"],default="published")
    args=parser.parse_args(argv)
    if args.verify is not None:
        if args.source is not None or args.output is not None:
            parser.error("--verify must be used without --source and --output")
        result=verify_pack(args.verify)
    else:
        if args.source is None or args.output is None:
            parser.error("both --source and --output are required to build a pack")
        result=build_pack(args.source,args.output,edition=args.edition)
    print(json.dumps(result,indent=2),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
