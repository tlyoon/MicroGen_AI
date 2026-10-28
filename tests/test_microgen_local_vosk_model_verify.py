"""Pinned offline model ZIP never escapes or overwrites the Dell-only tool root."""
import hashlib
import io
import stat
import zipfile
from pathlib import Path
import pytest
import microgen_local_vosk_model_verify as m


def _make_archive(tmp_path,monkeypatch,entries):
    archive=tmp_path/"official_vosk_small.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name,body in entries:
            z.writestr(name,body)
    monkeypatch.setattr(m,"ARCHIVE_SHA256",
                        hashlib.sha256(archive.read_bytes()).hexdigest())
    return archive,tmp_path/m.MODEL_NAME


def test_pinned_model_writes_only_safe_new_destination(tmp_path,monkeypatch):
    archive,dest=_make_archive(tmp_path,monkeypatch,[
       (f"{m.MODEL_NAME}/am/final.mdl",b"weights"),
       (f"{m.MODEL_NAME}/graph/words.txt",b"test"),
    ])
    receipt=m.unpack_verified_model_archive(archive,dest)
    assert receipt["files"]==2
    assert receipt["publication_allowed"] is False
    assert (dest/"am"/"final.mdl").read_bytes()==b"weights"
    assert (tmp_path/"model_provenance.json").is_file()
    with pytest.raises(m.ModelArchiveError,match="existing"):
        m.unpack_verified_model_archive(archive,dest)


@pytest.mark.parametrize("unsafe",["escape","absolute","symlink","root"])
def test_rejects_untrusted_zip_members_before_extraction(tmp_path,monkeypatch,unsafe):
    entries=[(f"{m.MODEL_NAME}/am/final.mdl",b"weights")]
    if unsafe=="escape":entries.append((f"{m.MODEL_NAME}/../unsafe.txt",b"bad"))
    if unsafe=="absolute":entries.append(("/absolute.txt",b"bad"))
    if unsafe=="root":entries.append((f"{m.MODEL_NAME}",b"bad"))
    archive,dest=_make_archive(tmp_path,monkeypatch,entries)
    if unsafe=="symlink":
        # Unix symlink payload masquerading as model graph.
        with zipfile.ZipFile(archive,"a") as z:
            info=zipfile.ZipInfo(f"{m.MODEL_NAME}/graph/link")
            info.create_system=3
            info.external_attr=(stat.S_IFLNK | 0o777)<<16
            z.writestr(info,b"../../outside")
        monkeypatch.setattr(m,"ARCHIVE_SHA256",
                            hashlib.sha256(archive.read_bytes()).hexdigest())
    with pytest.raises(m.ModelArchiveError):
        m.unpack_verified_model_archive(archive,dest)
    assert not dest.exists()


def test_archive_sha_must_be_preapproved(tmp_path,monkeypatch):
    archive,dest=_make_archive(tmp_path,monkeypatch,
       [(f"{m.MODEL_NAME}/am/final.mdl",b"weights")])
    monkeypatch.setattr(m,"ARCHIVE_SHA256","0"*64)
    with pytest.raises(m.ModelArchiveError,match="SHA-256"):
        m.unpack_verified_model_archive(archive,dest)
    assert not dest.exists()


def test_duplicate_member_not_silently_accepted(tmp_path,monkeypatch):
    archive,dest=_make_archive(tmp_path,monkeypatch,
       [(f"{m.MODEL_NAME}/am/final.mdl",b"weight-1"),
        (f"{m.MODEL_NAME}/am/final.mdl",b"weight-2")])
    with pytest.raises(m.ModelArchiveError,match="Duplicate"):
        m.unpack_verified_model_archive(archive,dest)
    assert not dest.exists()
