"""Bounded run command-line and checkpoint safety tests."""
import microgen_batch as batch


def test_bounded_parser_explicit_permission():
    parser=batch.build_parser()
    args=parser.parse_args(["--source-root","c","--work-root","d",
                            "--targets","2.5","--stop-after","tts"])
    assert args.stop_after == "tts"
    assert args.authorize_provider_usage is False


def test_stop_choices_never_include_publication():
    parser=batch.build_parser()
    choices=parser._option_string_actions["--stop-after"].choices
    assert "published" not in choices
    assert "tts" in choices


def test_existing_historical_mp4_cannot_be_published_by_bounded_run(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import patch
    src=tmp_path/"2"/"2.5"
    src.mkdir(parents=True)
    old=src/"slides.mp4"
    old.write_bytes(b"protected old movie")
    stage=tmp_path/"work"/"2.5"
    stage.mkdir(parents=True)
    args=SimpleNamespace(stop_after="tts",figure_extraction_only=False,
          multipart=False,rebuild_unverified=False,
          source_root=tmp_path,repo=tmp_path,work_root=tmp_path/"work",
          source_wait=0,commit="head",stage_retries=0,
          main_py="python",docling_py="docling")
    completed={k:"done" for k in batch.STAGES[:batch.STAGES.index("tts")+1]}
    fingerprint={k:"known" for k in completed}
    reports=[]
    with patch.object(batch,"prepare_stage",return_value=(stage,
                    {"completed":completed,"dependency_fingerprints":fingerprint},
                    stage/".microgen_checkpoint.json")), \
         patch.object(batch.quality,"published_manifest_valid",return_value=False), \
         patch.object(batch,"stage_valid",return_value=True), \
         patch.object(batch.quality,"dependency_fingerprint",return_value="known"), \
         patch.object(batch,"publish") as published, \
         patch.object(batch,"run_subprocess") as executed:
        batch.process_one(args,"2.5",reports)
    assert reports[0]["status"]=="bounded_stage_complete"
    assert reports[0]["stop_after"]=="tts"
    assert reports[0]["published"] is False
    assert old.read_bytes()==b"protected old movie"
    published.assert_not_called()
    executed.assert_not_called()
