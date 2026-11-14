import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_no_samples_installed():
    body = client.get("/api/samples").json()
    assert body["violin"]["available"] is False and body["violin"]["notes"] == {}


def test_lists_only_samples_that_exist(data_dir):
    folder = data_dir / "samples" / "violin"
    folder.mkdir(parents=True)
    (folder / "A4.wav").write_bytes(b"RIFF")
    (folder / "index.json").write_text(json.dumps({"A4": "A4.wav", "C5": "C5.wav", "E5": "../../x.wav"}))

    violin = client.get("/api/samples").json()["violin"]
    assert violin == {"available": True, "base_url": "/api/samples/violin/", "notes": {"A4": "A4.wav"}}

    sample = client.get("/api/samples/violin/A4.wav")
    assert sample.status_code == 200 and sample.content == b"RIFF"
    assert sample.headers["content-type"] == "audio/wav"


def test_sample_paths_are_restricted(data_dir):
    folder = data_dir / "samples" / "violin"
    folder.mkdir(parents=True)
    (folder / "index.json").write_text("{}")
    for path in ("violin/index.json", "violin/C5.wav", "violin/..%2f..%2fmeta.wav", "Violin/A4.wav"):
        assert client.get(f"/api/samples/{path}").status_code == 404
