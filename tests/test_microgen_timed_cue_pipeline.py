"""Offline integration checks for the opt-in TTS stage, no provider calls."""
import json
import os
from pathlib import Path
from unittest import mock

import pytest

import text_to_speech_v25
import microgen_timed_cue_tts
from microgen_quality import dependency_fingerprint
from microgen_timed_cue_planner import PLAN_FILE

from test_microgen_timed_cue_tts import input_stage


def _mock_call(stage, monkeypatch, *, enable_env=False):
    monkeypatch.chdir(stage)
    monkeypatch.delenv("MICROGEN_TIMED_CUES", raising=False)
    if enable_env:
        monkeypatch.setenv("MICROGEN_TIMED_CUES","1")
    fake={"cue_count":4,"slide_count":2,"provider":"gemini_flash_lite_tts","voice":"Kore"}
    items=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))["slides"]
    with (
        mock.patch("microgen_tts_provider_policy.require_formal_provider",
                   return_value="gemini"),
        mock.patch("microgen_flash_tts._load_gemini_keys_from_microvid"),
        mock.patch.object(text_to_speech_v25,"_speech_items",return_value=items),
        mock.patch("microgen_pronunciation.audit_slide_items",return_value=[]),
        mock.patch("microgen_tts_lexicon.check_lexicon_slides",return_value=[]),
        mock.patch.object(microgen_timed_cue_tts,"produce_measured_cue_audio",
                          return_value=fake) as cue,
        mock.patch.object(text_to_speech_v25,"_run_flash_batch") as legacy,
    ):
        text_to_speech_v25.main()
    return cue,legacy


def test_planned_timed_cues_use_existing_formal_gemini_path(tmp_path,monkeypatch):
    s=input_stage(tmp_path)
    cue,legacy=_mock_call(s,monkeypatch)
    cue.assert_called_once_with(s)
    legacy.assert_not_called()


def test_opt_in_auto_plan_checks_source_without_paid_request(tmp_path,monkeypatch):
    s=input_stage(tmp_path)
    (s/PLAN_FILE).unlink()
    cue,legacy=_mock_call(s,monkeypatch,enable_env=True)
    cue.assert_called_once_with(s)
    legacy.assert_not_called()
    assert (s/PLAN_FILE).is_file()


def test_standard_tts_path_stays_unchanged_without_plan(tmp_path,monkeypatch):
    s=input_stage(tmp_path)
    (s/PLAN_FILE).unlink()
    cue,legacy=_mock_call(s,monkeypatch)
    cue.assert_not_called()
    legacy.assert_called_once()


def test_tts_dependency_invalidates_on_cue_mode_and_plan(tmp_path,monkeypatch):
    s=input_stage(tmp_path)
    for name in ("text_to_speech_v25.py","microgen_flash_tts.py",
                 "microgen_timed_cue_tts.py","microgen_timed_cue_planner.py"):
        (s/name).write_text("source code v1",encoding="utf8")
    plan=s/PLAN_FILE
    plan.unlink()
    monkeypatch.setenv("MICROGEN_TIMED_CUES","0")
    old=dependency_fingerprint(s,"tts")
    monkeypatch.setenv("MICROGEN_TIMED_CUES","1")
    opt_in=dependency_fingerprint(s,"tts")
    assert old!=opt_in
    plan.write_text("source-tied plan",encoding="utf8")
    included=dependency_fingerprint(s,"tts")
    assert included!=opt_in
