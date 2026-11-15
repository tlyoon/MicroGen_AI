"""No-provider replay of verified previous figure mapping response caches."""
import hashlib,json
from pathlib import Path

from microgen_mapping_cache_recovery import reuse_verified_mapping_cache


def prepare_campaign(root, campaign, *, sha, revision="a"*40):
    parent=root/campaign
    stage=parent/"2.7"
    stage.mkdir(parents=True)
    (stage/"source.pdf").write_bytes(b"immutable-test-source")
    (parent/".microgen_bounded_provider_authorization.json").write_text(
        json.dumps({
            "publication_authorized":False,
            "scope":{"source_sha256":sha,"host":"hp","stop_after":"acceptance",
                     "code_revision":revision}
        }),encoding="utf8")
    (stage/".microgen_checkpoint.json").write_text(
        json.dumps({"package_commit":revision,"completed":{"figure_extraction":True}}),
        encoding="utf8")
    return stage


def test_attested_same_source_cache_transfers_no_failed_receipts(tmp_path):
    sha=hashlib.sha256(b"immutable-test-source").hexdigest()
    old=prepare_campaign(tmp_path,"older",sha=sha)
    new=prepare_campaign(tmp_path,"newer",sha=sha,revision="b"*40)
    cache=old/".microgen_mapping_cache";cache.mkdir()
    original={"key":"c"*64,"response":"fig_7.png : \"UNLABELED\" : SKIP"}
    (cache/"page_3_mapping_0000.json").write_text(json.dumps(original),encoding="utf8")
    (old/".microgen_private_failed_provider.json").write_text("failed",encoding="utf8")
    result=reuse_verified_mapping_cache(new,checkpoint_root=tmp_path,require_hp=False)
    assert result["responses_copied"]==1
    assert result["status"]=="SOURCE_BOUND_REPLIES_COPIED_REQUIRE_CURRENT_PROMPT_REHASH"
    assert json.loads((new/".microgen_mapping_cache"/"page_3_mapping_0000.json"
                       ).read_text())==original
    assert not (new/".microgen_private_failed_provider.json").exists()
    assert reuse_verified_mapping_cache(
        new,checkpoint_root=tmp_path,require_hp=False
    )["responses_copied"]==0


def test_wrong_source_grant_or_path_cannot_import(tmp_path):
    sha=hashlib.sha256(b"immutable-test-source").hexdigest()
    old=prepare_campaign(tmp_path,"older",sha=sha)
    new=prepare_campaign(tmp_path,"newer",sha="f"*64)
    cache=old/".microgen_mapping_cache";cache.mkdir()
    (cache/"page_3_captions.json").write_text(
        json.dumps({"key":"a"*64,"response":"Figure 2.12"}),encoding="utf8")
    assert reuse_verified_mapping_cache(
        new,checkpoint_root=tmp_path,require_hp=False
    )["responses_copied"]==0
    assert not (new/".microgen_mapping_cache").exists()


def test_malformed_and_path_traversal_cache_names_ignored(tmp_path):
    sha=hashlib.sha256(b"immutable-test-source").hexdigest()
    old=prepare_campaign(tmp_path,"older",sha=sha)
    new=prepare_campaign(tmp_path,"newer",sha=sha)
    cache=old/".microgen_mapping_cache";cache.mkdir()
    (cache/"bad_name.json").write_text(
        json.dumps({"key":"f"*64,"response":"untrusted"}),encoding="utf8")
    (cache/"page_3_captions.json").write_text(
        json.dumps({"key":"X"*64,"response":"untrusted"}),encoding="utf8")
    assert reuse_verified_mapping_cache(
        new,checkpoint_root=tmp_path,require_hp=False
    )["responses_copied"]==0

def test_many_non_campaign_files_do_not_exhaust_campaign_scan(tmp_path):
    # Real HP checkpoint storage carries far more ordinary receipt/log files
    # than campaign directories. They must never silently disable reuse.
    sha=hashlib.sha256(b"immutable-test-source").hexdigest()
    old=prepare_campaign(tmp_path,"older",sha=sha)
    new=prepare_campaign(tmp_path,"newer",sha=sha)
    folder=old/".microgen_mapping_cache";folder.mkdir()
    response={"key":"a"*64,"response":"fig_1.png : \"Figure 2.10\" : Figure 2.10.png"}
    (folder/"page_1_mapping_0000.json").write_text(
        json.dumps(response),encoding="utf8")
    for index in range(450):
        (tmp_path/f"ordinary_receipt_{index:04d}.json").write_text(
            "{}",encoding="utf8")
    result=reuse_verified_mapping_cache(
        new,checkpoint_root=tmp_path,require_hp=False)
    assert result["responses_copied"]==1
    assert json.loads(
        (new/".microgen_mapping_cache"/"page_1_mapping_0000.json").read_text("utf8")
    )==response


def test_many_actual_campaign_directories_still_fail_closed(tmp_path):
    sha=hashlib.sha256(b"immutable-test-source").hexdigest()
    old=prepare_campaign(tmp_path,"older",sha=sha)
    new=prepare_campaign(tmp_path,"newer",sha=sha)
    cache=old/".microgen_mapping_cache";cache.mkdir()
    (cache/"page_1_captions.json").write_text(
        json.dumps({"key":"b"*64,"response":"Figure 2.10"}),encoding="utf8")
    for index in range(402):
        (tmp_path/f"empty_campaign_{index:04d}").mkdir()
    result=reuse_verified_mapping_cache(
        new,checkpoint_root=tmp_path,require_hp=False)
    assert result["status"]=="TOO_MANY_CAMPAIGNS_ABSTAINED"
    assert not (new/".microgen_mapping_cache").exists()
