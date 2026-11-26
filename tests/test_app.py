from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_version_reports_the_build(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "abc123")
    monkeypatch.setenv("BUILD_URL", "https://example.test/run/1")
    assert client.get("/version").json() == {"commit": "abc123", "build": "https://example.test/run/1"}


def test_version_without_build_info(monkeypatch):
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("BUILD_URL", raising=False)
    assert client.get("/version").json() == {"commit": "unknown", "build": "unknown"}
