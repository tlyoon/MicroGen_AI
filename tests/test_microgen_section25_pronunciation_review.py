import json
import wave
import pytest
from microgen_source_safe_orchestrator import digest
from microgen_section25_pronunciation_review import ReviewBundleError, _verify_expected_candidate

def wav(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),"wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        out.writeframes(bytes(48000))

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data),encoding="utf8")

def test_cdot_candidate_rejects_wrong_audio_hash(tmp_path):
    candidate=tmp_path/"QA_tts_cdot_20261019"/"slide5_corrected.wav"
    wav(candidate)
    script_hash="a"*64
    video_hash="b"*64
    save(candidate.parent/"qa_receipt.json",{"original_script_tts_sha256":script_hash,
        "source_mp4_sha256_preserved":video_hash,"voice":"en-US-Chirp-HD-F"})
    queue=tmp_path/"QA_tts_PR39_20261020"/"all_slide_listening_queue.json"
    save(queue,{"source_script_sha256":script_hash,
        "rows":[{"slide":5,"wav_sha256":digest(candidate)}]})
    args=(tmp_path,5,"QA_tts_cdot_20261019/slide5_corrected.wav","CDOT",script_hash,video_hash)
    assert _verify_expected_candidate(*args)["source_media_receipt_bound"]
    save(queue,{"source_script_sha256":script_hash,
        "rows":[{"slide":5,"wav_sha256":"invalid"}]})
    with pytest.raises(ReviewBundleError):
        _verify_expected_candidate(*args)

def test_y_candidate_rejects_wrong_video_hash(tmp_path):
    candidate=tmp_path/"QA_tts_y_20261019"/"slide10_corrected_y.wav"
    wav(candidate)
    save(candidate.parent/"qa_receipt.json",{
        "original_mp4_sha256_preserved":"a"*64,
        "slide10_new_sha256":digest(candidate),
        "single_configured_voice":"en-US-Chirp-HD-F"})
    args=(tmp_path,10,"QA_tts_y_20261019/slide10_corrected_y.wav",
          "Y_VALUE","b"*64,"a"*64)
    report=_verify_expected_candidate(*args)
    assert not report["phonetic_approved"]
    assert not report["voice_independently_authenticated"]
    with pytest.raises(ReviewBundleError):
        _verify_expected_candidate(*args[:-1],"c"*64)

def test_alt_trial_keeps_unverified_source_binding(tmp_path):
    candidate=tmp_path/"QA_tts_PR35_20261020"/"slide10_PR35_unapproved.wav"
    wav(candidate)
    save(candidate.parent/"repair_receipt.json",{
        "slide":10,"candidate_wav_sha256":digest(candidate),
        "repair_report":{"status":"ACOUSTIC_QA_UNAVAILABLE"}})
    report=_verify_expected_candidate(tmp_path,10,
       "QA_tts_PR35_20261020/slide10_PR35_unapproved.wav",
       "Y_VALUE_ALT","a"*64,"b"*64)
    assert not report["source_media_receipt_bound"]
    assert not report["phonetic_approved"]
