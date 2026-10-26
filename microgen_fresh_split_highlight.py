"""Offline source-bound split video candidate from freshly generated slides/WAVs.

Creates UNAPPROVED technical word-cue candidates and two or more videos.
Does not claim semantic, phonetic, narration, figure or publication approval.
Never writes or publishes into the input lesson directory.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
import wave
from bisect import bisect_right
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw


class PreviewError(ValueError):
    pass


FRAME_W, FRAME_H, FPS = 960, 540, 8
MIN_TOKEN_LENGTH = 5
STOP = frozenset("""about above after again being between could every first following
from going great here into these their there those this through which while
would value values figure figures slide slides graph graphs equations equation
example examples consider suppose using given shows shown where because such
also only with then before under over therefore these those just mathematical
what your were that them much make like than""".split())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        while data := f.read(1024 * 1024):
            digest.update(data)
    return digest.hexdigest()


def safe_token(value):
    token = str(value).lower().strip(".,;:!?()[]")
    return token if re.fullmatch(r"[a-z]+", token) else ""


def wav_evidence(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise PreviewError("Source WAV missing or symlinked")
    with wave.open(str(p), "rb") as w:
        params = (w.getframerate(), w.getnchannels(), w.getsampwidth())
        seconds = w.getnframes() / w.getframerate()
        frames = w.getnframes()
    if params != (24000, 1, 2) or not 0.1 < seconds < 600:
        raise PreviewError("Unsupported source narration WAV (requires mono 24kHz PCM16)")
    return {"sha256": sha(p), "seconds": seconds, "frames": frames}


def select_parts(durations, max_seconds=570.0):
    """Find minimum number of whole-slide parts; balance the durations."""
    if not durations or any(not math.isfinite(v) or not 0 < v < max_seconds for v in durations):
        raise PreviewError("Invalid original slide durations")
    if len(durations) == 1:
        return [(1, 1, durations[0])]
    boundaries = []
    n = len(durations)
    # Work with contiguous groups, optimize part count first and balance second.
    state = {0: (0, 0.0, ())}
    for end in range(1, n + 1):
        options = []
        for start in range(end):
            v = sum(durations[start:end])
            if v >= max_seconds or start not in state:
                continue
            count, penalty, path = state[start]
            total = sum(durations)
            ideal = total / math.ceil(total / max_seconds)
            options.append((count + 1, penalty + ((v - ideal) / ideal)**2,
                            path + ((start + 1, end, v),)))
        if options:
            state[end] = min(options, key=lambda x: (x[0], x[1]))
    if n not in state:
        raise PreviewError("Cannot split into under-10-minute whole-slide parts")
    boundaries = state[n][2]
    if [i for start, end, _ in boundaries for i in range(start, end + 1)] != list(range(1, n + 1)):
        raise PreviewError("Missing/duplicated slide in partition")
    return boundaries


def source_evidence(stage):
    stage = Path(stage).resolve(strict=True)
    if not (stage/"source.pdf").is_file() or not (stage/"slides.pdf").is_file():
        raise PreviewError("Missing source/PDF slide lineage")
    with fitz.open(stage/"slides.pdf") as doc:
        n = doc.page_count
    if not 1 <= n <= 100:
        raise PreviewError("Unexpected source slide count")
    src = [wav_evidence(stage/f"slide{i}.wav") for i in range(1, n + 1)]
    return {
        "source_pdf_sha256": sha(stage/"source.pdf"),
        "slides_pdf_sha256": sha(stage/"slides.pdf"),
        "slide_count": n,
        "audio": src,
        "all_voice_files_present": True,
    }


def _asr_words(audio_file, model):
    from vosk import KaldiRecognizer
    with wave.open(str(audio_file), "rb") as wav:
        recog = KaldiRecognizer(model, 24000)
        recog.SetWords(True)
        words = []
        while chunk := wav.readframes(6000):
            if recog.AcceptWaveform(chunk):
                words.extend(json.loads(recog.Result()).get("result", []))
        words.extend(json.loads(recog.FinalResult()).get("result", []))
    return [{
        "word": str(x["word"]), "start": float(x["start"]), "end": float(x["end"]),
        "conf": float(x["conf"])} for x in words
        if isinstance(x, dict) and all(k in x for k in ("word", "start", "end", "conf"))]


def _unique_slide_rects(page):
    found = {}
    for x0, y0, x1, y1, word, *_ in page.get_text("words"):
        token = safe_token(word)
        if len(token) < MIN_TOKEN_LENGTH or token in STOP:
            continue
        found.setdefault(token, []).append((float(x0), float(y0), float(x1), float(y1)))
    return {k:v[0] for k,v in found.items() if len(v) == 1}


def _make_part_audio(stage, indices, destination):
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise PreviewError("Do not overwrite existing candidate audio")
    with wave.open(str(target), "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(24000)
        for index in indices:
            with wave.open(str(stage/f"slide{index}.wav"), "rb") as w:
                if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, 24000):
                    raise PreviewError("Audio changed during concatenation")
                while buf := w.readframes(24000):
                    out.writeframesraw(buf)
    return wav_evidence(target)


def _get_slide_image(page):
    zoom = min(FRAME_W/page.rect.width, FRAME_H/page.rect.height)
    px = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    base = Image.new("RGB", (FRAME_W,FRAME_H), "white")
    shift = ((FRAME_W - px.width)//2, (FRAME_H - px.height)//2)
    base.paste(Image.frombytes("RGB", (px.width, px.height), px.samples), shift)
    return base, (zoom, shift)


def _draw_cue(frame, geometry, rect):
    scale, (dx, dy) = geometry
    x0,y0,x1,y1=rect
    # Strictly highlight the bounding box of an ASR-derived, unique PDF word.
    color = Image.new("RGBA", frame.size, (0,0,0,0))
    d = ImageDraw.Draw(color)
    box=(round(x0*scale+dx)-3,round(y0*scale+dy)-3,
         round(x1*scale+dx)+3,round(y1*scale+dy)+3)
    d.rectangle(box,fill=(255,191,50,85),outline=(228,78,18,230),width=3)
    return Image.alpha_composite(frame.convert("RGBA"),color).convert("RGB")


def _decoded_pcm_sha(mp4, ffmpeg):
    p = subprocess.Popen([str(ffmpeg),"-nostdin","-v","error","-i",str(mp4),
                          "-map","0:a:0","-f","s16le","-ar","24000","-ac","1","pipe:1"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    hash_ = hashlib.sha256()
    while chunk := p.stdout.read(1024*1024):
        hash_.update(chunk)
    detail=p.stderr.read()
    rc=p.wait(timeout=60)
    if rc:
        raise PreviewError("Audio decode failure: "+detail.decode("utf8","replace")[-500:])
    return hash_.hexdigest()


def _wav_pcm_sha(audio_file):
    hash_ = hashlib.sha256()
    with wave.open(str(audio_file),"rb") as w:
        while chunk := w.readframes(24000):
            hash_.update(chunk)
    return hash_.hexdigest()


def generate_unapproved_split_candidates(stage, output, model_dir, ffmpeg_path):
    stage=Path(stage).resolve(strict=True)
    out=Path(output).resolve(strict=False)
    if out.exists() or out.is_symlink() or out==stage or out.is_relative_to(stage) or stage.is_relative_to(out):
        raise PreviewError("Output must be fresh and outside protected input")
    ffmpeg=Path(ffmpeg_path).resolve(strict=True)
    model_dir=Path(model_dir).resolve(strict=True)
    if not ffmpeg.is_file() or not model_dir.is_dir():
        raise PreviewError("Required explicit offline tools missing")
    original=source_evidence(stage)
    durations=[x["seconds"] for x in original["audio"]]
    parts=select_parts(durations)
    out.mkdir(parents=True,exist_ok=False)
    from vosk import Model, SetLogLevel
    SetLogLevel(-1)
    recognizer=Model(str(model_dir))
    # Compute and persist SHA-bound recognition first, so partial audio/video
    # failures do not require another paid stage or repeat existing ASR.
    cues={}
    word_counts={}
    with fitz.open(stage/"slides.pdf") as pdf:
        for index in range(1,len(durations)+1):
            source=stage/f"slide{index}.wav"
            hypothesis=_asr_words(source,recognizer)
            rectangles=_unique_slide_rects(pdf[index-1])
            links=[]
            for rec in hypothesis:
                word=safe_token(rec["word"])
                if (word in rectangles and rec["conf"]>=0.60 and
                        0 <= rec["start"] < rec["end"] <= durations[index-1]+0.2):
                    links.append({"start":rec["start"],"end":rec["end"],
                                  "word":word,"box":rectangles[word],
                                  "conf":rec["conf"]})
            cues[index]=links
            word_counts[index]={"asr_word_count":len(hypothesis),
                                "candidate_pdf_word_matches":len(links),
                                "ambiguous_or_unmatched":len(hypothesis)-len(links)}
        # Claim only hypotheses; there is NO mathematical semantic approval.
        cue_packet={"schema_version":1,
            "status":"OFFLINE_ASR_PDF_WORD_CANDIDATES_NOT_APPROVED",
            "input_source_evidence":original,
            "slide_hypotheses":word_counts,
            "candidate_count":sum(len(x) for x in cues.values()),
            "slide_word_rectangles":{str(k):v for k,v in cues.items()},
            "phonetic_accuracy_verified":False,
            "spoken_mathematical_semantics_verified":False,
            "figure_highlight_alignment_verified":False,
            "publication_allowed":False}
        (out/"candidate_word_cues.json").write_text(
            json.dumps(cue_packet,indent=2,sort_keys=True),encoding="utf8")
        result=[]
        for part_num,(start,end,seconds) in enumerate(parts,1):
            subset=range(start,end+1)
            audio=out/f"part{part_num:02d}_source_pcm.wav"
            pcm_info=_make_part_audio(stage,subset,audio)
            if abs(pcm_info["seconds"]-seconds)>.01:
                raise PreviewError("Audio duration drift after concatenation")
            frames=[]
            transformations=[]
            for slide in subset:
                frame,trans=_get_slide_image(pdf[slide-1])
                frames.append(frame)
                transformations.append(trans)
            ends=[]
            cumulative=0.0
            for i in subset:
                cumulative+=durations[i-1]
                ends.append(cumulative)
            video=out/f"Thomas_2_5_part{part_num:02d}_UNAPPROVED.mp4"
            command=[str(ffmpeg),"-nostdin","-hide_banner","-loglevel","error","-n",
                     "-f","rawvideo","-pixel_format","rgb24",
                     "-video_size",f"{FRAME_W}x{FRAME_H}","-framerate",str(FPS),
                     "-i","pipe:0","-i",str(audio),"-map","0:v:0","-map","1:a:0",
                     "-c:v","libx264","-preset","ultrafast","-crf","29","-pix_fmt","yuv420p",
                     "-c:a","alac","-t",f"{seconds:.6f}","-movflags","+faststart",
                     str(video)]
            proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
                                  stderr=subprocess.PIPE)
            nframes=math.ceil(seconds*FPS)
            cue_frames=0
            cache={}
            try:
                for frame_id in range(nframes):
                    moment=(frame_id+0.5)/FPS
                    k=min(len(ends)-1,bisect_right(ends,moment))
                    slide=start+k
                    previous=ends[k-1] if k else 0.
                    relative=moment-previous
                    active=[(m["word"],m["start"],m["end"]) for m in cues[slide]
                            if m["start"]<=relative<m["end"]]
                    # Use a tuple stable across frames for source-bounded render cache.
                    signature=(k,tuple(active))
                    if signature not in cache:
                        if active:
                            selected=[m for m in cues[slide]
                                      if m["start"]<=relative<m["end"]]
                            img=frames[k]
                            for m in selected:
                                img=_draw_cue(img,transformations[k],m["box"])
                        else:
                            img=frames[k]
                        cache[signature]=img.tobytes()
                    if active:cue_frames+=1
                    proc.stdin.write(cache[signature])
                proc.stdin.close()
                rc=proc.wait(timeout=90)
                detail=proc.stderr.read().decode("utf8","replace")
                proc.stderr.close()
                if rc or not video.is_file():
                    raise PreviewError("FFmpeg failed: "+detail[-450:])
            except Exception:
                if proc.poll() is None:
                    proc.kill();proc.wait(timeout=10)
                raise
            from microgen_quality import check_video
            actual=check_video(video,expected_seconds=seconds,ffmpeg=str(ffmpeg))["seconds"]
            if not 0 < actual < 600 or abs(actual-seconds) > .35:
                raise PreviewError("Encoded video violates lecture duration or source clock")
            if _decoded_pcm_sha(video,ffmpeg)!=_wav_pcm_sha(audio):
                raise PreviewError("Encoded MP4 audio differs from original source WAVs")
            result.append({
                "part":part_num,"slides":list(subset),"video":video.name,
                "video_sha256":sha(video),"source_part_audio_sha256":sha(audio),
                "expected_seconds":seconds,"actual_seconds":actual,
                "frames_rendered":nframes,"frames_with_candidate_word_cues":cue_frames,
                "candidate_word_rectangles":sum(len(cues[i]) for i in subset),
                "pcm_bit_identical":True,
                "word_highlight_pixels_independently_verified":False,
                "figure_semantic_alignment_verified":False,
                "publication_allowed":False})
    # Recheck input bytes after expensive read/render to catch concurrent edits.
    if source_evidence(stage)!=original:
        raise PreviewError("Source PDF/WAV changed during render")
    report={
        "schema_version":1,"status":"FRESH_SOURCE_SPLIT_HIGHLIGHT_TECHNICAL_PREVIEW_NOT_APPROVED",
        "source_evidence":original,"cue_packet_sha256":sha(out/"candidate_word_cues.json"),
        "parts":result,"publication_allowed":False,
        "academic_qa_verified":False,
        "voice_identity_listening_verified":False,
        "phonetic_quality_verified":False,
        "figures_spoken_semantics_verified":False,
        "highlight_pixels_independently_verified":False}
    (out/"split_preview_receipt.json").write_text(json.dumps(report,indent=2,sort_keys=True),encoding="utf8")
    return {"parts":len(result),"part_durations":[x["actual_seconds"] for x in result],
            "candidate_cues":cue_packet["candidate_count"],
            "publication_allowed":False}


if __name__=="__main__":
    if len(sys.argv)!=5:
        raise SystemExit("Usage: python microgen_fresh_split_highlight.py STAGE NEW_OUTPUT VOSK_MODEL FFMPEG")
    print(generate_unapproved_split_candidates(*sys.argv[1:]),flush=True)
