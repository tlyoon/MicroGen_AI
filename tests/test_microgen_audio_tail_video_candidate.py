"""No original media mutation and no approval from scene/audio overhang claims."""
import json
from pathlib import Path
import pytest
import microgen_audio_tail_video_candidate as c
import microgen_legacy_audio_demux as r
from test_microgen_legacy_audio_demux import build_synthetic_legacy

def test_tail_render_requires_real_demux_receipt(tmp_path):
    _,stage,ff=build_synthetic_legacy(tmp_path)
    with pytest.raises((FileNotFoundError,c.LegacyRecoveryError)):
        c.render_audio_tail_candidate(stage,ffmpeg=ff)
    assert not (stage/"technical_candidate").exists()

def test_synthetic_audio_without_mismatch_is_not_enough(tmp_path):
    _,stage,ff=build_synthetic_legacy(tmp_path)
    r.recover_legacy_scene_wavs(stage,ffmpeg=ff)
    with pytest.raises(c.LegacyRecoveryError):
        c.render_audio_tail_candidate(stage,ffmpeg=ff)
    assert not (stage/"technical_candidate").exists()

def test_rejects_forged_tail_wav_without_overwriting(tmp_path,monkeypatch):
    source,stage,ff=build_synthetic_legacy(tmp_path)
    evidence=source/".microgen_legacy_video_evidence.json"
    data=json.loads(evidence.read_text())
    data["candidate_seconds"]=1.85
    evidence.write_text(json.dumps(data))
    monkeypatch.setattr(r,"check_video",lambda path:{"seconds":1.85})
    r.recover_legacy_scene_wavs(stage,ffmpeg=ff)
    receipt=stage/"legacy_mp4_audio_receipt.json"
    obj=json.loads(receipt.read_text())
    obj["audio_beyond_video_end"]["tail_sha256"]="0"*64
    receipt.write_text(json.dumps(obj))
    with pytest.raises(c.LegacyRecoveryError):
        c.render_audio_tail_candidate(stage,ffmpeg=ff)
    assert not (stage/"technical_candidate").exists()


def test_lossless_tail_extension_preserves_decoded_pcm_on_short_video(tmp_path,monkeypatch):
    source,stage,ff=build_synthetic_legacy(tmp_path)
    report=source/".microgen_legacy_video_evidence.json"
    data=json.loads(report.read_text())
    data["candidate_seconds"]=1.85
    report.write_text(json.dumps(data))
    # This fixture deliberately models a 1.85 s visual timeline plus 2.4 s
    # decoded soundtrack. Genuine content timestamps are not being asserted.
    monkeypatch.setattr(r,"check_video",lambda _:{"seconds":1.85})
    r.recover_legacy_scene_wavs(stage,ffmpeg=ff)
    candidate=c.render_audio_tail_candidate(stage,ffmpeg=ff)
    assert candidate["decoded_audio_pcm_sha256_unchanged"]
    assert candidate["general_publication_format_approved"] is False
    assert candidate["candidate_video_seconds"]>=2.3
    assert candidate["candidate_video_seconds"]<600
    assert candidate["publication_allowed"] is False
    assert (stage/"technical_candidate_lossless_timed"/"slides_full_audio_ALAC_NOT_PUBLISHED.mp4").is_file()
