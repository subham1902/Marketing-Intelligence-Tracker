"""Public-mode protections: owner-only actions, rate limits, operator key. No network."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPETE_DUCKDB_PATH", str(tmp_path / "g.duckdb"))
    monkeypatch.setenv("COMPETE_DATA_DIR", str(tmp_path))
    from api import guard
    from fastapi.testclient import TestClient
    from pipeline.config import get_settings
    from pipeline.storage.duckdb_store import Warehouse

    get_settings.cache_clear()
    guard.reset()
    Warehouse(tmp_path / "g.duckdb").close()
    from api.main import app

    with TestClient(app) as c:
        yield c
    guard.reset()
    get_settings.cache_clear()


def test_local_mode_is_unrestricted(client, monkeypatch) -> None:
    monkeypatch.delenv("COMPETE_PUBLIC_MODE", raising=False)
    r = client.put("/api/settings/llm", json={"mode": "off"})
    assert r.status_code == 200
    assert client.get("/api/health").json()["public_mode"] is False


def test_public_mode_owner_only_actions(client, monkeypatch) -> None:
    monkeypatch.setenv("COMPETE_PUBLIC_MODE", "true")
    monkeypatch.setenv("COMPETE_ADMIN_TOKEN", "s3cret-token-value")
    for method, path, body in [
        ("put", "/api/settings/llm", {"mode": "off"}),
        ("post", "/api/settings/llm/test", {"mode": "off"}),
        ("post", "/api/competitors", {"name": "X Co"}),
        ("delete", "/api/competitors/anything", None),
        ("post", "/api/pipeline/run", {}),
    ]:
        kw = {"json": body} if body is not None else {}
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 403, path
        assert "site owner" in r.json()["error"]["message"]
    ok = client.put("/api/settings/llm", json={"mode": "off"}, headers={"X-Admin-Token": "s3cret-token-value"})
    assert ok.status_code == 200
    assert client.get("/api/health").json()["public_mode"] is True


def test_default_admin_token_never_works(client, monkeypatch) -> None:
    monkeypatch.setenv("COMPETE_PUBLIC_MODE", "true")
    monkeypatch.setenv("COMPETE_ADMIN_TOKEN", "change-me")
    r = client.put("/api/settings/llm", json={"mode": "off"}, headers={"X-Admin-Token": "change-me"})
    assert r.status_code == 403


def test_rate_limit_per_ip(client, monkeypatch) -> None:
    monkeypatch.setenv("COMPETE_PUBLIC_MODE", "true")
    codes = [client.post("/api/assistant/chat", json={"message": "hi"},
                         headers={"X-Forwarded-For": "203.0.113.7"}).status_code for _ in range(31)]
    assert codes[:30] == [200] * 30 and codes[30] == 429
    # A different visitor is not affected.
    other = client.post("/api/assistant/chat", json={"message": "hi"}, headers={"X-Forwarded-For": "198.51.100.2"})
    assert other.status_code == 200
    # Behind Caddy, X-Real-IP (set by the proxy) wins over a spoofed X-Forwarded-For.
    spoof = client.post("/api/assistant/chat", json={"message": "hi"},
                        headers={"X-Real-IP": "203.0.113.7", "X-Forwarded-For": "10.9.9.9"})
    assert spoof.status_code == 429


def test_operator_key_from_env_is_default_and_hidden(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPERATOR_LLM_API_KEY", "gsk_" + "x" * 30)
    from api import llm_settings
    from pipeline.config import Settings

    data = llm_settings.load(Settings())
    assert data["mode"] == "openai_compatible" and data["source"] == "env"
    view = client.get("/api/settings/llm").json()
    assert "x" * 30 not in json.dumps(view)
