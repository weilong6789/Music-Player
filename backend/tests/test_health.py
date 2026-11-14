import os
import stat

from fastapi.testclient import TestClient

from app import config
from app.main import app

client = TestClient(app)


def test_health_reports_both_engines():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert set(body["engines"]) == {"audiveris", "homr"}
    for engine in body["engines"].values():
        assert isinstance(engine["available"], bool)
        assert engine["detail"]


def test_audiveris_found_via_env_var(tmp_path, monkeypatch):
    binary = tmp_path / "Audiveris"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv(config.AUDIVERIS_ENV_VAR, str(binary))

    engine = client.get("/api/health").json()["engines"]["audiveris"]
    assert engine == {"available": True, "detail": str(binary)}


def test_audiveris_bad_env_var_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv(config.AUDIVERIS_ENV_VAR, str(tmp_path / "missing"))

    engine = client.get("/api/health").json()["engines"]["audiveris"]
    assert engine["available"] is False
    assert config.AUDIVERIS_ENV_VAR in engine["detail"]


def test_audiveris_missing_without_env_var(monkeypatch):
    monkeypatch.delenv(config.AUDIVERIS_ENV_VAR, raising=False)
    monkeypatch.setattr(config, "AUDIVERIS_DEFAULT_BIN", config.ROOT_DIR / "nope")
    monkeypatch.setenv("PATH", os.devnull)

    engine = client.get("/api/health").json()["engines"]["audiveris"]
    assert engine["available"] is False
