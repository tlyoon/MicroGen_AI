"""Opt-in, crash-safe *private* Flash-Lite TTS producer for measured element cues.

One whole-lecture render_batch() provides single-engine, consistent-voice
Gemini 3.8 Flash-Lite TTS, Gemini 3.8 Flash fallback, and only after both
fail a bounded, owner-authorized Google Cloud Chirp 3 fallback. All cue chunks are concatenated as PCM, SHA-bound to slide text and PDFs,
then staged and verified before any output is installed. Existing WAVs and
receipts are never overwritten. No local model, ASR, or publication.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

PLAN_FILE = ".microgen_timed_cue_plan.json"
MAX_CUES = 120


class CueTTSError(RuntimeError):
    """Incomplete or unsafe source-grounded cue audio generation."""


def _sha(path: Path) -> str:
    from microgen_quality import sha256
    return sha256(path)


def _verified_plan(stage: Path) -> tuple[dict, list[str]]:
    from microgen_timed_highlight_contract import _equivalent_text
    import fitz

    plan_path = stage / PLAN_FILE
    if plan_path.is_symlink() or not plan_path.is_file():
        raise CueTTSError("No verified timed-cue plan supplied")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf8"))
        if (not isinstance(plan, dict)
                or plan.get("schema_version") != 1
                or plan.get("publication_allowed") is not False
                or plan.get("semantic_mapping_certified", False) is not False
                or plan.get("planning_method") not in {
                    "source_pdf_overlap_conservative",
                    "source_pdf_grounded_semantic_screen",
                }):
            raise CueTTSError("Unsupported or untrusted cue plan")
        pdf = stage / "slides.pdf"
        script = stage / "script_tts.json"
        if (plan.get("slides_pdf_sha256") != _sha(pdf)
                or plan.get("script_tts_sha256") != _sha(script)):
            raise CueTTSError("Source PDF or narration drifted since cue planning")
        narration = json.loads(script.read_text(encoding="utf8"))["slides"]
        rows = plan.get("slides")
        with fitz.open(str(pdf)) as deck:
            count = deck.page_count
            if (not 1 <= count <= 200 or not isinstance(rows, list)
                    or len(rows) != count or len(narration) != count):
                raise CueTTSError("Cue plan does not cover all slides")
            all_fragments = []
            semantic_used = False
            for slide_no, (row, source_row) in enumerate(zip(rows,narration), 1):
                if (not isinstance(row, dict) or not isinstance(source_row, dict)
                        or row.get("slide") != slide_no
                        or source_row.get("slide") != slide_no):
                    raise CueTTSError("Cue/narration slide order mismatch")
                single = stage / f"slide{slide_no}.pdf"
                if (single.is_symlink() or not single.is_file()
                        or row.get("slide_pdf_sha256") != _sha(single)):
                    raise CueTTSError("Unverified source slide page")
                with fitz.open(str(single)) as one:
                    if (one.page_count != 1 or
                        _equivalent_text(one[0].get_text()) !=
                        _equivalent_text(deck[slide_no-1].get_text())):
                        raise CueTTSError("Source deck differs from numbered slide")
                    page = one[0]
                    cues = row.get("cues")
                    if not isinstance(cues,list) or not 1 <= len(cues) <= 40:
                        raise CueTTSError("Missing or excessive slide cues")
                    fragments=[]
                    names=set()
                    for cue_no, cue in enumerate(cues,1):
                        if not isinstance(cue,dict):
                            raise CueTTSError("Invalid cue plan row")
                        name = cue.get("element_id")
                        spoken=cue.get("spoken_text")
                        label=cue.get("pdf_text")
                        coords=cue.get("pdf_bbox")
                        if (not isinstance(name,str) or not name
                            or name in names or not isinstance(spoken,str)
                            or not 10 <= len(spoken) <= 10000
                            or not isinstance(label,str)
                            or not 2 <= len(label) <= 400
                            or not isinstance(coords,list) or len(coords)!=4):
                            raise CueTTSError("Unsafe or duplicate cue element")
                        names.add(name)
                        try:
                            box=fitz.Rect(coords)
                        except (ValueError,TypeError) as exc:
                            raise CueTTSError("Invalid cue bbox") from exc
                        extracted = _equivalent_text(page.get_textbox(box))
                        if (box.is_empty or box.is_infinite or
                            not page.rect.contains(box) or
                            _equivalent_text(label) not in extracted):
                            raise CueTTSError("Element not grounded in source PDF")
                        if "question_context_role" in cue:
                            from microgen_timed_cue_planner import (
                                QUESTION_REFLECTION_ROLE,
                                question_reflection_source_block,
                                _pdf_text_blocks,
                            )
                            if (cue["question_context_role"] != QUESTION_REFLECTION_ROLE
                                    or "semantic_source_quote" in cue
                                    or "pdf_bboxes" in cue
                                    or "semantic_source_quotes" in cue):
                                raise CueTTSError("Invalid question reflection provenance")
                            actual_blocks=_pdf_text_blocks(page)
                            anchor=question_reflection_source_block(
                                spoken,cue_no,len(cues),actual_blocks)
                            if (anchor is None
                                    or label != actual_blocks[anchor][1]
                                    or any(abs(a-b)>0.01 for a,b in zip(
                                        coords,actual_blocks[anchor][0]))):
                                raise CueTTSError(
                                    "Question reflection not source-grounded")
                        elif cue_no == len(cues):
                            # A tampered plan cannot remove the explicit
                            # contextual (non-claim) provenance marker and
                            # pretend this was an ordinary lexical match.
                            from microgen_timed_cue_planner import (
                                QUESTION_REFLECTION_ROLE,
                                question_reflection_source_block,
                                _pdf_text_blocks, _lexical_match,
                            )
                            actual_blocks=_pdf_text_blocks(page)
                            if question_reflection_source_block(
                                    spoken,cue_no,len(cues),actual_blocks) is not None:
                                all_spoken=[
                                    item.get("spoken_text") for item in cues
                                    if isinstance(item,dict)]
                                if len(all_spoken)==len(cues) and all(
                                        isinstance(s,str) for s in all_spoken):
                                    expected,_=_lexical_match(
                                        slide_no,all_spoken,actual_blocks,
                                        allow_unanchored=True)
                                    expected_cue=expected[-1]
                                    if (expected_cue is not None and
                                            expected_cue.get("question_context_role")
                                            == QUESTION_REFLECTION_ROLE):
                                        raise CueTTSError(
                                            "Missing question reflection provenance")
                        if "pdf_bboxes" in cue:
                            from microgen_cue_semantic_mapping import (
                                compact, numbers, MAX_GROUP_BLOCKS,
                            )
                            regions = cue["pdf_bboxes"]
                            labels = cue.get("pdf_texts")
                            quotes = cue.get("semantic_source_quotes")
                            if (plan["planning_method"] != "source_pdf_grounded_semantic_screen"
                                    or "semantic_source_quote" in cue
                                    or not isinstance(regions,list)
                                    or not isinstance(labels,list)
                                    or not isinstance(quotes,list)
                                    or not 2 <= len(regions) <= MAX_GROUP_BLOCKS
                                    or len(regions) != len(labels)
                                    or len(labels) != len(quotes)):
                                raise CueTTSError("Unsafe multi-element cue provenance")
                            # Do not accept an arbitrary union rectangle:
                            # every selected region must contain its own
                            # quoted, exact PDF text and preserve its location.
                            checked=[]
                            for region, item_text, quote in zip(regions, labels, quotes):
                                if (not isinstance(region,list) or len(region)!=4
                                        or any(type(v) not in (int,float) for v in region)
                                        or not isinstance(item_text,str)
                                        or not 8 <= len(item_text) <= 350
                                        or not isinstance(quote,str)
                                        or not 8 <= len(quote) <= 200):
                                    raise CueTTSError("Malformed source element group")
                                try:
                                    region_box=fitz.Rect(region)
                                except (ValueError,TypeError) as exc:
                                    raise CueTTSError("Invalid group rectangle") from exc
                                raw=_equivalent_text(page.get_textbox(region_box))
                                if (region_box.is_empty or region_box.is_infinite
                                        or not page.rect.contains(region_box)
                                        or _equivalent_text(item_text) not in raw
                                        or len(compact(quote)) < 8
                                        or compact(quote) not in compact(item_text)):
                                    raise CueTTSError("Multi-element quote not PDF grounded")
                                checked.append(region_box)
                            union=checked[0]
                            for region_box in checked[1:]:
                                union |= region_box
                            if (any(abs(a-b)>0.01 for a,b in zip(union,box))
                                    or union.width*union.height >
                                    page.rect.width*page.rect.height*0.40
                                    or not numbers(spoken).issubset(
                                        numbers(" ".join(labels)))):
                                raise CueTTSError("Group bounds or numerical claim unverified")
                            semantic_used = True
                        elif "semantic_source_quotes" in cue or "pdf_texts" in cue:
                            raise CueTTSError("Unpaired multi-element provenance")
                        elif "semantic_source_quote" in cue:
                            from microgen_cue_semantic_mapping import compact, numbers
                            quote = cue["semantic_source_quote"]
                            if (plan["planning_method"] != "source_pdf_grounded_semantic_screen"
                                    or not isinstance(quote,str)
                                    or not 8 <= len(quote) <= 200
                                    or len(compact(quote)) < 8 or compact(quote) not in extracted
                                    or not numbers(spoken).issubset(numbers(label))):
                                raise CueTTSError("Semantic claim lacks exact PDF evidence")
                            semantic_used = True
                        fragments.append(spoken)
                    original=str(source_row.get("tts_text") or
                                 source_row.get("narration") or "")
                    if _equivalent_text(" ".join(fragments)) != _equivalent_text(original):
                        raise CueTTSError("Cue plan changes or omits narration")
                    all_fragments.extend(fragments)
            if len(all_fragments) != plan.get("total_cues"):
                raise CueTTSError("Cue inventory mismatch")
            if (semantic_used != (plan["planning_method"] ==
                                  "source_pdf_grounded_semantic_screen")):
                raise CueTTSError("Semantic cue provenance does not match planning method")
            if not 1 <= len(all_fragments) <= MAX_CUES:
                raise CueTTSError("Global cue batch is too large for single voice")
    except (KeyError, TypeError, IndexError, ValueError, OSError, json.JSONDecodeError) as exc:
        if isinstance(exc,CueTTSError):
            raise
        raise CueTTSError("Unreadable source-bound cue plan") from exc
    return plan, all_fragments


def produce_measured_cue_audio(stage: Path, *, speak=None) -> dict:
    """Install only to a fresh, private isolated stage; rollback on failures.

    A test may pass an offline speak(text,spec)->WAV callback. By default,
    render_batch() uses the established Flash-Lite provider/key pool and
    whole-batch same-voice fallback. No Cloud fallback without owner opt-in,
    and this producer deliberately does not support it yet.
    """
    from microgen_flash_tts import (
        render_batch, _merge_wavs, DEFAULT_VOICE,
    )
    from microgen_timed_highlight_contract import (
        MANIFEST, inspect_timed_highlights,
    )
    from microgen_tts_provenance import (
        make_record,verify_manifest,verify_records,write_manifest,
    )
    from microgen_quality import check_wavs
    from text_to_speech_v25 import normalize_scientific_speech

    stage = Path(stage)
    if stage.is_symlink() or not stage.is_dir():
        raise CueTTSError("The cue TTS stage must be an isolated real directory")
    plan, fragments = _verified_plan(stage)
    count = len(plan["slides"])
    # No original files, previously accepted TTS, or partial transactions
    # are ever overwritten to make this feature appear to pass.
    output_files = [f"slide{i}.wav" for i in range(1,count+1)]
    output_files += [MANIFEST, ".microgen_tts_provenance.json"]
    for name in output_files:
        candidate=stage/name
        if candidate.exists() or candidate.is_symlink():
            raise CueTTSError(f"Existing verified or partial TTS output: {name}")
    if (stage/"highlight_chunks").exists() or (stage/"highlight_chunks").is_symlink():
        raise CueTTSError("Existing cue audio directory must not be overwritten")
    if (stage/".microgen_tts_cache").exists() or (stage/".microgen_tts_cache").is_symlink():
        raise CueTTSError("Existing immutable TTS evidence cache must be preserved")
    source_signature = (
        _sha(stage/"slides.pdf"), _sha(stage/"script_tts.json"),
        _sha(stage/PLAN_FILE),
        *(_sha(stage/f"slide{i}.pdf") for i in range(1,count+1)),
    )
    texts=[normalize_scientific_speech(x) for x in fragments]
    if any(not text for text in texts):
        raise CueTTSError("Empty normalized cue narration")
    from microgen_timed_highlight_contract import _equivalent_text
    index=0
    source_rows=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))["slides"]
    for row,source in zip(plan["slides"],source_rows):
        n=len(row["cues"])
        actual=" ".join(texts[index:index+n])
        original=normalize_scientific_speech(str(
            source.get("tts_text") or source.get("narration") or ""))
        if _equivalent_text(actual)!=_equivalent_text(original):
            raise CueTTSError("Per-cue pronunciation normalization changed the source script")
        index+=n
    voice = os.environ.get("MICROGEN_TTS_VOICE",DEFAULT_VOICE)
    with tempfile.TemporaryDirectory(prefix=".microgen-cue-tts-",
                                     dir=str(stage)) as temp_dir:
        scratch=Path(temp_dir)
        # The standing owner contract authorizes TTS as required by private
        # content generation. Cloud is only the FINAL whole-batch fallback,
        # and only if a finite character ceiling was signed into the private
        # provider scope. Standalone/direct calls remain Gemini-only unless
        # the same bounded Cloud settings are explicitly supplied.
        cloud_allowed=(os.environ.get("MICROGEN_TTS_ENABLE_CLOUD_FALLBACK")=="1")
        if cloud_allowed:
            cap=os.environ.get(
                "MICROGEN_TTS_CLOUD_FALLBACK_MAX_CHARACTERS","").strip()
            if not cap.isdigit() or int(cap)<1:
                raise CueTTSError("Cloud fallback lacks a finite source-bound budget")
            if sum(len(text) for text in texts)>int(cap):
                # Cloud has insufficient consent for this long transcript,
                # but both Gemini 3.8 choices remain fully usable.
                cloud_allowed=False
                print("[tts] Cloud-only character budget below source cue "
                      "inventory; preserving Gemini 3.8 primary/fallback "
                      "without paid Cloud calls",flush=True)
        report=render_batch(texts,scratch/"ready",voice=voice,
                            allow_cloud=cloud_allowed,speak=speak)
        model,provider,actual_voice=report["model"],report["engine"],report["voice"]
        authorized={
            "gemini_flash_lite_tts": ("gemini-3.8-flash-lite-tts",voice),
            "gemini_flash_tts": ("gemini-3.8-flash-tts",voice),
        }
        if cloud_allowed:
            authorized["google_cloud_chirp3"]=(
                "chirp3-hd",f"en-US-Chirp3-HD-{voice}")
        if (provider not in authorized
                or (model,actual_voice)!=authorized[provider]):
            raise CueTTSError("Cue batch returned unauthorized voice/provider")
        prepared=scratch/"prepared"
        prepared.mkdir()
        for name in ("slides.pdf","script_tts.json"):
            shutil.copy2(stage/name,prepared/name)
        for i in range(1,count+1):
            shutil.copy2(stage/f"slide{i}.pdf",prepared/f"slide{i}.pdf")
        chunk_dir=prepared/"highlight_chunks"
        chunk_dir.mkdir()
        from microgen_quality import sha256
        rows=[]
        record_inputs=[]
        records=[]
        flat_index=0
        for slide_no,plan_row in enumerate(plan["slides"],1):
            outputs=[]
            cues=[]
            for cue_no,cue in enumerate(plan_row["cues"],1):
                flat_index+=1
                source = scratch/"ready"/f"slide{flat_index:02}.wav"
                if not source.is_file():
                    raise CueTTSError("Missing TTS cue WAV in single-voice batch")
                name=f"highlight_chunks/slide{slide_no}_cue{cue_no}.wav"
                dest=prepared/name
                shutil.copy2(source,dest)
                outputs.append(source.read_bytes())
                cues.append({
                    **cue,"audio_chunk":name,
                    "audio_chunk_sha256":sha256(dest),
                })
            full_wav=_merge_wavs(outputs)
            target=prepared/f"slide{slide_no}.wav"
            target.write_bytes(full_wav)
            rows.append({
                "slide":slide_no,
                "slide_pdf_sha256":sha256(prepared/f"slide{slide_no}.pdf"),
                "slide_wav_sha256":sha256(target),
                "cues":cues,
            })
            # Keep the same normalization and provenance as the current
            # production Flash TTS stage, not a second TTS policy.
            script=json.loads((prepared/"script_tts.json").read_text(encoding="utf8"))
            src=script["slides"][slide_no-1]
            normalized=normalize_scientific_speech(str(
                src.get("tts_text") or src.get("narration") or ""))
            record_inputs.append(normalized)
            key=hashlib.sha256(json.dumps(
                [normalized,provider,model,actual_voice,"en-US",1.0,
                 "global","microgen-measured-cues-v1"],
                ensure_ascii=False,sort_keys=True).encode("utf8")).hexdigest()
            records.append(make_record(
                slide=slide_no,path=target,text=normalized,provider=provider,
                key=key,voice_name=actual_voice,language_code="en-US",
                speaking_rate=1.0,location="global",
            ))
        verify_records(prepared,records,record_inputs)
        write_manifest(prepared,records,record_inputs)
        manifest={
            "schema_version":1,
            "timing_method":"measured_ordered_pcm_chunks",
            "slides_pdf_sha256":sha256(prepared/"slides.pdf"),
            "script_tts_sha256":sha256(prepared/"script_tts.json"),
            "slides":rows,"publication_allowed":False,
        }
        (prepared/MANIFEST).write_text(
            json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf8")
        inspect_timed_highlights(prepared)
        wav_evidence=check_wavs(prepared,count)
        from microgen_tts_risk_register import (
            build_risk_register,save_immutable_risk_report,
        )
        from microgen_pronunciation_evidence_pipeline import (
            build_post_tts_evidence,save_stage_evidence,
        )
        qa_cache=prepared/".microgen_tts_cache"
        qa_cache.mkdir()
        risk=build_risk_register(
            source_rows,normalize_scientific_speech,
            wav_evidence["seconds"],wav_sha256=wav_evidence["sha256"])
        save_immutable_risk_report(qa_cache,risk)
        pronunciation=build_post_tts_evidence(
            prepared,source_rows,normalize_scientific_speech)
        save_stage_evidence(prepared,pronunciation)
        if (source_signature != (
            _sha(stage/"slides.pdf"),_sha(stage/"script_tts.json"),
            _sha(stage/PLAN_FILE),
            *(_sha(stage/f"slide{i}.pdf") for i in range(1,count+1))
        )):
            raise CueTTSError("Source changed during paid TTS requests")
        if (any((stage/name).exists() or (stage/name).is_symlink()
                for name in output_files) or
                (stage/"highlight_chunks").exists() or
                (stage/".microgen_tts_cache").exists()):
            raise CueTTSError("Concurrent TTS outputs appeared; refuse replacement")
        installed=[]
        try:
            # Create only new filenames using atomic exclusive hard links.
            # Unlike os.replace, an unrelated accepted WAV cannot be clobbered
            # by a concurrent worker between preflight and commit.
            for i in range(1,count+1):
                name=f"slide{i}.wav"
                os.link(prepared/name,stage/name)
                installed.append(stage/name)
            destination=stage/"highlight_chunks"
            destination.mkdir(exist_ok=False)
            installed.append(destination)
            for chunk in chunk_dir.iterdir():
                os.link(chunk,destination/chunk.name)
            cache_destination=stage/".microgen_tts_cache"
            cache_destination.mkdir(exist_ok=False)
            installed.append(cache_destination)
            for item in qa_cache.iterdir():
                os.link(item,cache_destination/item.name)
            provenance=prepared/".microgen_tts_provenance.json"
            os.link(provenance,stage/provenance.name)
            installed.append(stage/provenance.name)
            # Last writer-wins is unsafe for the receipt: exclusive create.
            os.link(prepared/MANIFEST,stage/MANIFEST)
            installed.append(stage/MANIFEST)
            inspect_timed_highlights(stage)
            verify_manifest(stage,record_inputs)
        except Exception:
            for path in reversed(installed):
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
            raise
        return {
            "status":"PRIVATE_SOURCE_BOUND_MEASURED_TTS_CUES_VERIFIED",
            "provider":provider, "voice":actual_voice,
            "slide_count":count,"cue_count":len(fragments),
            "publication_allowed":False,
        }
