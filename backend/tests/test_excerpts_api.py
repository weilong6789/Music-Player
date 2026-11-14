import shutil
import stat

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.pipeline import omr
from app.pipeline.omr.audiveris import AudiverisEngine
from app.pipeline.omr.base import OMRError
from conftest import make_score, n, write_xml
from test_pipeline_parts import make_pdf

client = TestClient(app)


class FakeEngine:
    def __init__(self, name, xml=None, available=True, error=None):
        self.name, self.xml, self._available, self.error = name, xml, available, error
        self.calls: list[list] = []

    def available(self):
        return self._available

    def detail(self):
        return "fake"

    def run(self, image_paths, out_dir):
        self.calls.append(list(image_paths))
        if self.error:
            raise OMRError(self.error)
        dest = out_dir / f"{self.name}.musicxml"
        shutil.copyfile(self.xml, dest)
        return dest


@pytest.fixture
def engines(monkeypatch, simple_xml):
    fakes = {name: FakeEngine(name, simple_xml) for name in ("audiveris", "homr")}
    monkeypatch.setattr(omr, "ENGINES", fakes)
    return fakes


def png_bytes() -> bytes:
    ok, data = cv2.imencode(".png", np.full((300, 400, 3), 255, np.uint8))
    assert ok
    return data.tobytes()


def upload(name, data, **form):
    return client.post("/api/excerpts", files={"file": (name, data)}, data=form)


def test_pdf_upload_runs_the_pipeline(engines, tmp_path, data_dir):
    pdf = make_pdf(tmp_path / "Mahler 5.pdf", pages=2).read_bytes()
    response = upload("Mahler 5.pdf", pdf)
    assert response.status_code == 201
    meta = response.json()

    assert meta["title"] == "Mahler 5"
    assert meta["source_type"] == "pdf"
    assert meta["engine"] == "audiveris"  # auto picks Audiveris for PDFs
    assert meta["page_count"] == 2
    assert meta["cleanup"] == {"perspective": False, "deskew": False, "threshold": False}
    assert (meta["tempo_bpm"], meta["tempo_source"]) == (72, "marking")
    assert (meta["measure_count"], meta["note_count"]) == (2, 5)
    assert len(engines["audiveris"].calls[0]) == 2 and not engines["homr"].calls

    folder = data_dir / "excerpts" / meta["id"]
    assert sorted(p.name for p in folder.iterdir()) == [
        "meta.json", "omr", "original.pdf", "pages", "score.musicxml",
    ]
    assert (folder / "omr" / "audiveris.musicxml").is_file()

    assert client.get("/api/excerpts").json() == [meta]
    assert client.get(f"/api/excerpts/{meta['id']}").json() == meta
    page = client.get(f"/api/excerpts/{meta['id']}/pages/2")
    assert page.status_code == 200 and page.headers["content-type"] == "image/png"
    assert client.get(f"/api/excerpts/{meta['id']}/pages/3").status_code == 404
    score = client.get(f"/api/excerpts/{meta['id']}/score")
    assert score.status_code == 200 and b"<score-partwise" in score.content
    assert client.get(f"/api/excerpts/{meta['id']}/score?format=mei").status_code == 404


def test_image_upload_prefers_homr_and_straightens(engines):
    meta = upload("photo.JPG", png_bytes()).json()
    assert meta["engine"] == "homr"
    assert meta["source_type"] == "image"
    assert meta["cleanup"] == {"perspective": True, "deskew": True, "threshold": False}


def test_cleanup_flags_override_the_defaults(engines):
    meta = upload("scan.png", png_bytes(), deskew="false", perspective="false", threshold="true").json()
    assert meta["cleanup"] == {"perspective": False, "deskew": False, "threshold": True}
    assert meta["cleanup_applied"] == ["threshold"]


def test_auto_falls_back_when_the_first_engine_fails(engines):
    engines["homr"].error = "model exploded"
    meta = upload("photo.png", png_bytes()).json()
    assert meta["engine"] == "audiveris"
    assert meta["warnings"] == ["homr failed, so audiveris was used instead."]


def test_auto_falls_back_when_the_first_engine_returns_no_notes(engines, tmp_path):
    from music21 import note

    engines["homr"].xml = write_xml(make_score([[note.Rest(quarterLength=4.0)]]), tmp_path / "empty.musicxml")
    assert upload("photo.png", png_bytes()).json()["engine"] == "audiveris"


def test_auto_skips_an_engine_that_is_not_installed(engines):
    engines["homr"]._available = False
    meta = upload("photo.png", png_bytes()).json()
    assert meta["engine"] == "audiveris" and meta["warnings"] == []


def test_explicit_engine_failure_is_an_error_and_leaves_nothing_behind(engines, data_dir):
    engines["homr"].error = "model exploded"
    response = upload("photo.png", png_bytes(), engine="homr")
    assert response.status_code == 422
    assert "model exploded" in response.json()["detail"]
    assert not engines["audiveris"].calls
    assert client.get("/api/excerpts").json() == []
    assert list((data_dir / "excerpts").iterdir()) == []


def test_missing_engine_is_an_error(engines):
    engines["audiveris"]._available = False
    response = upload("photo.png", png_bytes(), engine="audiveris")
    assert response.status_code == 422 and "isn't installed" in response.json()["detail"]


def test_accidental_rule_is_applied_and_recorded(engines, tmp_path):
    engines["homr"].xml = write_xml(
        make_score([[n("F#4", printed=True), n("F#4", printed=False), n("G4", length=2.0)]]),
        tmp_path / "sharp.musicxml",
    )
    meta = upload("photo.png", png_bytes(), accidental_rule="note").json()
    assert meta["accidental_rule"] == "note"

    from music21 import converter

    score = converter.parse(client.get(f"/api/excerpts/{meta['id']}/score").content, format="musicxml")
    assert [p.nameWithOctave for p in score.pitches] == ["F#4", "F4", "G4"]


@pytest.mark.parametrize(
    "name, data, form, status",
    [
        ("notes.txt", b"hello", {}, 415),
        ("scan.png", b"", {}, 422),
        ("scan.png", b"not an image", {}, 422),
        ("scan.pdf", b"not a pdf", {}, 422),
        ("scan.png", None, {"engine": "nope"}, 422),
        ("scan.png", None, {"accidental_rule": "nope"}, 422),
    ],
)
def test_bad_uploads(engines, name, data, form, status):
    response = upload(name, png_bytes() if data is None else data, **form)
    assert response.status_code == status
    assert client.get("/api/excerpts").json() == []


def test_delete(engines, data_dir):
    excerpt_id = upload("scan.png", png_bytes()).json()["id"]
    assert client.delete(f"/api/excerpts/{excerpt_id}").status_code == 204
    assert client.get(f"/api/excerpts/{excerpt_id}").status_code == 404
    assert client.delete(f"/api/excerpts/{excerpt_id}").status_code == 404
    assert not (data_dir / "excerpts" / excerpt_id).exists()


@pytest.mark.parametrize("excerpt_id", ["nope", "..", "0123456789ab", "%2e%2e"])
def test_unknown_ids_are_404(excerpt_id):
    assert client.get(f"/api/excerpts/{excerpt_id}").status_code == 404
    assert client.get(f"/api/excerpts/{excerpt_id}/score").status_code == 404


def test_library_is_newest_first(engines, monkeypatch):
    from app.pipeline import importer

    stamps = iter(["2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"])

    class Clock:
        @staticmethod
        def now(tz=None):
            class Stamp:
                def isoformat(self, timespec=None):
                    return next(stamps)

            return Stamp()

    monkeypatch.setattr(importer, "datetime", Clock)
    upload("old.png", png_bytes())
    upload("new.png", png_bytes())
    assert [m["title"] for m in client.get("/api/excerpts").json()] == ["new", "old"]


# --- Audiveris wrapper against a stand-in binary ------------------------------


def fake_audiveris(tmp_path, body: str):
    binary = tmp_path / "Audiveris"
    binary.write_text("#!/bin/sh\n" + body)
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    return binary


def test_audiveris_wrapper_merges_one_export_per_page(tmp_path, monkeypatch, simple_xml):
    # Mimics the real CLI: -batch -export -output <dir> -- <inputs>, one .mxl per input in a subfolder.
    binary = fake_audiveris(
        tmp_path,
        f"""
[ "$1" = "-batch" ] && [ "$2" = "-export" ] && [ "$3" = "-output" ] && [ "$5" = "--" ] || exit 2
out="$4"; shift 5
for input in "$@"; do
  stem=$(basename "$input" .png)
  mkdir -p "$out/$stem"
  cp "{simple_xml}" "$out/$stem/score.xml"
  (cd "$out/$stem" && python3 -m zipfile -c "$stem.mxl" score.xml && rm score.xml)
done
""",
    )
    monkeypatch.setenv(config.AUDIVERIS_ENV_VAR, str(binary))
    pages = [tmp_path / "page-1.png", tmp_path / "page-2.png"]
    for page in pages:
        page.write_bytes(png_bytes())
    out = tmp_path / "omr"
    out.mkdir()

    result = AudiverisEngine().run(pages, out)

    from music21 import converter

    assert result == out / "audiveris.musicxml"
    assert len(converter.parse(result).parts[0].getElementsByClass("Measure")) == 4
    assert [p.name for p in out.iterdir()] == ["audiveris.musicxml"]


def test_audiveris_wrapper_reports_failures(tmp_path, monkeypatch):
    monkeypatch.setenv(config.AUDIVERIS_ENV_VAR, str(fake_audiveris(tmp_path, "echo 'no staves found' >&2; exit 3\n")))
    page = tmp_path / "page-1.png"
    page.write_bytes(png_bytes())
    with pytest.raises(OMRError, match="no staves found"):
        AudiverisEngine().run([page], tmp_path)


def test_audiveris_wrapper_reports_missing_export(tmp_path, monkeypatch):
    monkeypatch.setenv(config.AUDIVERIS_ENV_VAR, str(fake_audiveris(tmp_path, "exit 0\n")))
    page = tmp_path / "page-1.png"
    page.write_bytes(png_bytes())
    with pytest.raises(OMRError, match="without exporting"):
        AudiverisEngine().run([page], tmp_path)


# --- PATCH ------------------------------------------------------------------


def test_patch_tempo_marks_it_as_entered_by_the_user(engines):
    excerpt_id = upload("scan.png", png_bytes()).json()["id"]
    meta = client.patch(f"/api/excerpts/{excerpt_id}", json={"tempo_bpm": 96}).json()
    assert (meta["tempo_bpm"], meta["tempo_source"]) == (96, "user")
    assert client.get(f"/api/excerpts/{excerpt_id}").json() == meta


def test_patch_title_leaves_tempo_alone(engines):
    excerpt_id = upload("scan.png", png_bytes()).json()["id"]
    meta = client.patch(f"/api/excerpts/{excerpt_id}", json={"title": "  Don Juan, bars 1-12 "}).json()
    assert meta["title"] == "Don Juan, bars 1-12"
    assert (meta["tempo_bpm"], meta["tempo_source"]) == (72, "marking")


@pytest.mark.parametrize("body", [{"tempo_bpm": 5}, {"tempo_bpm": 900}, {"title": ""}, {"title": "   "}])
def test_patch_rejects_bad_values(engines, body):
    excerpt_id = upload("scan.png", png_bytes()).json()["id"]
    assert client.patch(f"/api/excerpts/{excerpt_id}", json=body).status_code == 422


def test_patch_unknown_excerpt():
    assert client.patch("/api/excerpts/0123456789ab", json={"tempo_bpm": 96}).status_code == 404
