"""HP-only no-billing source-stage contract: completeness before cloud stages."""
import hashlib
import json
from pathlib import Path
from unittest import mock

import pytest
import pymupdf

import microgen_batch as batch


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _source_case(tmp_path, count=2):
    stage = tmp_path / "stage"
    stage.mkdir()
    root = stage / "pages"
    root.mkdir()
    document = pymupdf.open()
    for i in range(count):
        page = document.new_page(width=210,height=297)
        page.insert_text((30,30),f"Source page {i+1}")
    document.save(stage/"source.pdf")
    document.close()
    marker = {
        "status":"OFFLINE_SOURCE_FIGURE_EXTRACTION_COMPLETE",
        "source_sha256": _sha(stage/"source.pdf"),
        "page_count":count,
        "pages":[],
        "gemini_invoked":False,
        "tts_invoked":False,
        "publication_allowed":False,
    }
    with pymupdf.open(stage/"source.pdf") as book:
        for i in range(1,count+1):
            folder=root/f"page_{i}"
            folder.mkdir()
            pg=book[i-1]
            single=pymupdf.open()
            single.insert_pdf(book,from_page=i-1,to_page=i-1)
            single.save(folder/f"page_{i}.pdf")
            single.close()
            (folder/f"page_{i}.png").write_bytes(pg.get_pixmap().tobytes("png"))
            marker["pages"].append({
                "page":i,
                "png_sha256":_sha(folder/f"page_{i}.png"),
                "pdf_sha256":_sha(folder/f"page_{i}.pdf"),
                "figures":[],
            })
    (stage/"figure_extraction_receipt.json").write_text(json.dumps(marker))
    return stage


def test_source_stage_accepts_all_pages_only_with_receipt(tmp_path):
    stage=_source_case(tmp_path)
    assert batch.source_page_extraction_valid(stage)
    assert batch.stage_valid(stage,"figure_extraction",stage)


@pytest.mark.parametrize("tamper",[
    "missing_marker","missing_second_page","missing_png","alter_png",
    "alter_pdf","change_source","forge_approval","missing_fig","source_page_count",
])
def test_incomplete_or_tampered_pdf_source_stage_fails(tmp_path,tamper):
    stage=_source_case(tmp_path)
    marker=stage/"figure_extraction_receipt.json"
    record=json.loads(marker.read_text())
    if tamper=="missing_marker":marker.unlink()
    elif tamper=="missing_second_page":
        (stage/"pages"/"page_2"/"page_2.pdf").unlink()
    elif tamper=="missing_png":
        (stage/"pages"/"page_1"/"page_1.png").unlink()
    elif tamper=="alter_png":
        (stage/"pages"/"page_1"/"page_1.png").write_bytes(b"fake PNG")
    elif tamper=="alter_pdf":
        (stage/"pages"/"page_2"/"page_2.pdf").write_bytes(b"fake PDF")
    elif tamper=="change_source":
        (stage/"source.pdf").write_bytes(b"different content")
    elif tamper=="forge_approval":
        record["publication_allowed"]=True
        marker.write_text(json.dumps(record))
    elif tamper=="missing_fig":
        record["pages"][0]["figures"]=[{"name":"fig_1.png","sha256":"0"*64}]
        marker.write_text(json.dumps(record))
    elif tamper=="source_page_count":
        record["page_count"]=1
        marker.write_text(json.dumps(record))
    assert batch.source_page_extraction_valid(stage) is False


def test_offline_mode_parser_is_opt_in_and_single_host():
    p=batch.build_parser()
    base=["--source-root","a","--work-root","b","--targets","2.5"]
    assert p.parse_args(base).figure_extraction_only is False
    assert p.parse_args(base+["--figure-extraction-only"]).figure_extraction_only is True


def test_source_only_preflight_never_checks_paid_sdk_or_latex():
    commands=[]
    def fake_run(args,**kwargs):
        commands.append(args)
        class Result:
            returncode=0
            stdout="offline OK"
            stderr=""
        return Result()
    with mock.patch.object(batch.subprocess,"run",side_effect=fake_run), \
         mock.patch.object(batch.shutil,"which",side_effect=AssertionError("pdflatex unused")):
        batch.preflight("python","docling-python",figure_extraction_only=True)
    assert len(commands)==2
    assert "pymupdf" in commands[0][-1]
    assert "docling" in commands[1][-1]
    assert not any("google" in " ".join(c).lower() for c in commands)


def test_source_only_process_stops_before_paid_production(tmp_path,monkeypatch):
    stage=_source_case(tmp_path)
    checkpoint=stage/".microgen_checkpoint.json"
    from types import SimpleNamespace
    args=SimpleNamespace(figure_extraction_only=True,multipart=False,
        docling_py="offline",main_py="local",repo=tmp_path,
        source_root=tmp_path,work_root=tmp_path,source_wait=0,commit="pinned",
        rebuild_unverified=False,stage_retries=0)
    report=[]
    with mock.patch.object(batch,"prepare_stage",
            return_value=(stage,{"completed":{"figure_extraction":"before"},
                                "dependency_fingerprints":{}},checkpoint)), \
         mock.patch.object(batch.quality,"published_manifest_valid",return_value=False), \
         mock.patch.object(batch,"run_subprocess") as subprocess_run, \
         mock.patch.object(batch,"mark_complete") as mark_complete, \
         mock.patch.object(batch,"publish") as publish:
        batch.process_one(args,"2.5",report)
    assert len(report)==1
    assert report[0]["status"]=="offline_figure_extraction_complete"
    assert report[0]["published"] is False
    assert report[0]["gemini_or_tts_invoked"] is False
    assert subprocess_run.call_count<=1
    assert publish.call_count==0
