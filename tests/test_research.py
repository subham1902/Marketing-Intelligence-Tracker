"""Research provider, normalization and API tests (no network, no credits)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pipeline.research.provider import ContextDevProvider, ProviderError
from pipeline.research.service import ResearchRequest, build_task, normalize, run_research

ANSWER = {
    "partial": False,
    "request_id": "req-1",
    "json_content": {
        "executive_summary": "EV adoption is rising.",
        "industry_overview": "Two-wheelers lead.",
        "market_trends": ["Trend A"],
        "risks": ["Risk A"],
        "findings": [
            {
                "title": "Plant expansion",
                "category": "manufacturing",
                "entity": "Acme Motors",
                "summary": "Acme expands capacity.",
                "significance": 9,
                "confidence": 85,
                "kind": "verified_fact",
                "source_urls": ["https://www.acme.in/news/plant/"],
            },
            {
                "title": "Invented claim",
                "category": "policy",
                "kind": "verified_fact",
                "summary": "Cites a URL the provider never read.",
                "source_urls": ["https://nowhere.example/x"],
            },
        ],
    },
    "sources": [
        "https://acme.in/news/plant",
        "https://pib.gov.in/release?id=1",
        "https://nowhere.example/x",
    ],
}

SEARCH = {
    "query": "q",
    "request_id": "s1",
    "cache_metadata": {"status": "miss", "age_ms": 0},
    "results": [
        {"url": "https://pib.gov.in/release?id=1", "title": "PIB release", "description": "Snippet",
         "relevance": "high"},
    ],
}


def _transport(answer_status: int = 200, answer_body: object = ANSWER) -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["Authorization"] == "Bearer test-key"
        body = json.loads(req.content)
        if req.url.path.endswith("/web/answers"):
            assert body["mode"] == "fast"
            assert len(body["task"]) <= 2000
            if isinstance(answer_body, str):
                return httpx.Response(answer_status, text=answer_body)
            return httpx.Response(answer_status, json=answer_body)
        if req.url.path.endswith("/web/search"):
            return httpx.Response(200, json=SEARCH)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _provider(**kw) -> ContextDevProvider:
    prov = ContextDevProvider("test-key", transport=_transport(**kw))
    prov._sleep = lambda s: None  # no real backoff in tests
    return prov


def test_retries_429_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "1"}, json={"message": "slow"})
        return httpx.Response(200, json=ANSWER)

    prov = ContextDevProvider("test-key", transport=httpx.MockTransport(handler))
    prov._sleep = lambda s: None
    assert prov.answer("t", {}).sources and calls["n"] == 2


REQ = ResearchRequest(objective="Research Indian EV market", industry="EV", companies=["Acme"],
                      source_preferences=["government"])


def test_build_task_contains_context() -> None:
    t = build_task(REQ)
    assert "India" in t and "EV" in t and "Acme" in t and "government" in t
    assert len(t) <= 2000


def test_run_research_validates_citations() -> None:
    status = {
        "acme.in/news/plant": "ok",
        "pib.gov.in/release?id=1": "unknown",
        "nowhere.example/x": "dead",
    }
    res = run_research(
        "r1", REQ, _provider(), company_domains={"acme.in"}, link_checker=lambda urls: status
    )
    assert len(res.sources) == 3
    by_domain = {s["domain"]: s for s in res.sources}
    assert by_domain["pib.gov.in"]["source_type"] == "government"
    assert by_domain["pib.gov.in"]["title"] == "PIB release"  # from Search, exact URL
    assert by_domain["acme.in"]["source_type"] == "company"
    assert by_domain["acme.in"]["title"] is None  # never invented

    good, bad = res.findings
    assert good["kind"] == "verified_fact" and good["source_ids"]
    assert good["category"] == "expansion"
    assert good["significance"] == 5 and good["confidence"] == 0.85
    assert bad["kind"] == "analysis" and "dead_citation" in bad["flags"]
    assert res.report["executive_summary"] == "EV adoption is rising."


@pytest.mark.parametrize("status,code", [(401, "unauthorized"), (402, "credits_exhausted"),
                                         (429, "rate_limited"), (500, "provider_failed")])
def test_provider_errors_are_mapped(status: int, code: str) -> None:
    with pytest.raises(ProviderError) as ei:
        _provider(answer_status=status, answer_body={"message": "nope"}).answer("t", {})
    assert ei.value.code == code
    assert "test-key" not in str(ei.value)


def test_invalid_json_is_handled() -> None:
    with pytest.raises(ProviderError) as ei:
        _provider(answer_body="<html>").answer("t", {})
    assert ei.value.code == "invalid_json"


def test_missing_key_raises() -> None:
    with pytest.raises(ProviderError) as ei:
        ContextDevProvider("")
    assert ei.value.code == "missing_key"


def test_normalize_tolerates_garbage() -> None:
    res = normalize("r", {"findings": ["x", {"title": ""}, {"title": "ok", "category": 5}]},
                    ["not-a-url", "https://a.com"], industry=None)
    assert [f["title"] for f in res.findings] == ["ok"]
    assert res.findings[0]["category"] == "other"


# ------------------------------- API layer -------------------------------- #
@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COMPETE_DUCKDB_PATH", str(tmp_path / "r.duckdb"))
    monkeypatch.setenv("COMPETE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "test-key")
    from fastapi.testclient import TestClient
    from pipeline.config import get_settings
    from pipeline.storage.duckdb_store import Warehouse

    get_settings.cache_clear()
    Warehouse(tmp_path / "r.duckdb").close()

    from api.main import app
    from api.routers import research

    monkeypatch.setattr(research, "provider_factory", lambda: _provider())
    import pipeline.research.service as svc

    monkeypatch.setattr(svc, "check_links", lambda urls: {})
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_research_end_to_end(client) -> None:
    r = client.post("/research", json={"objective": "Research Indian EV market", "industry": "EV"})
    assert r.status_code == 202
    run_id = r.json()["id"]
    # TestClient runs background tasks before returning.
    run = client.get(f"/research/{run_id}").json()
    assert run["status"] == "completed", run
    assert run["source_count"] == 3 and run["finding_count"] == 2
    assert run["result"]["executive_summary"]
    assert len(client.get(f"/research/{run_id}/sources").json()) == 3
    assert len(client.get(f"/research/{run_id}/findings").json()) == 2
    assert client.get("/research").json()[0]["id"] == run_id
    feed = client.get("/findings?category=expansion").json()
    assert feed["total"] == 1
    assert client.get("/research/nope").status_code == 404


def test_research_provider_failure_marks_failed(client, monkeypatch) -> None:
    from api.routers import research

    monkeypatch.setattr(research, "provider_factory", lambda: _provider(answer_status=402))
    run_id = client.post("/research", json={"objective": "Research Indian EV market"}).json()["id"]
    run = client.get(f"/research/{run_id}").json()
    assert run["status"] == "failed" and run["error_code"] == "credits_exhausted"
    assert client.get("/health").status_code == 200


def test_research_without_key_fails_cleanly(client, monkeypatch) -> None:
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "")
    r = client.post("/research", json={"objective": "Research Indian EV market"})
    assert r.status_code == 202
    assert r.json()["status"] == "failed" and r.json()["error_code"] == "missing_key"
    assert client.get("/research/config").json()["live_available"] is False


def test_build_task_keeps_rules_with_long_objective() -> None:
    req = ResearchRequest(
        objective="x" * 1200,
        industry="EV",
        companies=["A"] * 12,
        source_preferences=["official_company", "government", "tenders", "regulatory", "news", "industry"],
    )
    t = build_task(req)
    assert len(t) <= 2000 and t.startswith("Rules:")


def test_normalize_list_overview_and_object_items() -> None:
    res = normalize(
        "r", {"industry_overview": ["a", "b"], "risks": [{"risk": "Cell imports"}]}, [], industry=None
    )
    assert res.report["industry_overview"] == "a b"
    assert res.report["risks"] == ["Cell imports"]


# ---- link-check classification (release hardening) ----


def _client_raising(monkeypatch, exc: Exception) -> None:
    """Make check_links' httpx.Client raise ``exc`` on every request."""
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    def fake_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)


def test_tls_failure_is_unknown_not_dead(monkeypatch) -> None:
    """Indian gov sites often have broken cert chains; that is not evidence the page is gone."""
    import ssl

    from pipeline.research.service import check_links

    err = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
    err.__cause__ = ssl.SSLCertVerificationError(1, "certificate verify failed")
    _client_raising(monkeypatch, err)
    assert check_links(["https://pib.gov.in/x"]) == {"pib.gov.in/x": "unknown"}


def test_dns_failure_is_dead(monkeypatch) -> None:
    from pipeline.research.service import check_links

    _client_raising(monkeypatch, httpx.ConnectError("[Errno -2] Name or service not known"))
    assert check_links(["https://nope.example/x"]) == {"nope.example/x": "dead"}


def test_sebi_is_regulatory_not_government() -> None:
    from pipeline.research.service import classify_source

    assert classify_source("https://www.sebi.gov.in/filings/x.html") == "regulatory"
    assert classify_source("https://pib.gov.in/PressRelease.aspx") == "government"
    assert classify_source("https://gem.gov.in/bid/1") == "tender"


def test_outside_window_is_flagged_not_hidden() -> None:
    from datetime import date

    content = {
        "findings": [
            {"title": "Old", "date": "2022-07-28", "source_urls": []},
            {"title": "Recent", "date": "2026-10-01", "source_urls": []},
            {"title": "Month only", "date": "2026-05", "source_urls": []},
            {"title": "Undated", "source_urls": []},
        ]
    }
    res = normalize("r", content, [], industry=None, window_start=date(2026, 5, 22))
    flagged = {f["title"]: "outside_window" in f["flags"] for f in res.findings}
    assert flagged == {"Old": True, "Recent": False, "Month only": False, "Undated": False}
