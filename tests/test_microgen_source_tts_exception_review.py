"""False approval/source-tamper guards for risk packet review."""
import json
import pathlib
import pytest
from microgen_source_tts_exception_review import RiskPacketError,build_current_tts_risk_review
from microgen_fresh_source_cues import FreshCueError


def test_missing_or_invalid_path_fails(tmp_path):
    with pytest.raises((FileNotFoundError,RiskPacketError,FreshCueError)):
        build_current_tts_risk_review(tmp_path,tmp_path/"missing",tmp_path/"asr",
                                      tmp_path/"risk")


def test_existing_output_refused(tmp_path):
    with pytest.raises((FileNotFoundError,RiskPacketError,FreshCueError)):
        build_current_tts_risk_review(tmp_path,tmp_path/"bad",
                                      tmp_path/"bad",tmp_path)
