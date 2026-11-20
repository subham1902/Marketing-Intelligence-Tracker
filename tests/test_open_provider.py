"""Open (free) research provider tests: fixtures only, no network."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import httpx
import pytest

from pipeline.research.open_provider import (
    OpenConfig,
    OpenResearchProvider,
    categorize,
    quote_in_text,
)
from pipeline.research.provider import ProviderError
from pipeline.research.service import ResearchRequest, run_research

NOW = datetime.now(UTC)
RECENT = format_datetime(NOW - timedelta(days=3))
OLD = format_datetime(NOW - timedelta(days=400))

GNEWS_RSS = f"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Acme Motors launches new electric scooter - Auto News</title>
<link>https://news.google.com/rss/articles/abc</link><pubDate>{RECENT}</pubDate>
<source url="https://autonews.example">Auto News</source></item>
<item><title>Ancient EV story - Old Paper</title>
<link>https://news.google.com/rss/articles/old</link><pubDate>{OLD}</pubDate>
<source url="https://old.example">Old Paper</source></item>
</channel></rss>"""

PIB_RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Cabinet approves electric bus scheme for cities</title>
<link>https://pib.gov.in/PressReleasePage.aspx?PRID=1</link></item>
<item><title>Unrelated cultural festival</title><link>https://pib.gov.in/PressReleasePage.aspx?PRID=2</link></item>
</channel></rss>"""

ARTICLE_TEXT = (
    "Acme Motors has opened a new battery plant in Pune with capacity of 5 GWh. "
    "The company said production will start next quarter. Analysts expect lower costs."
)
ARTICLE_HTML = f"""<html><head><title>Acme opens plant</title>
<meta property="article:published_time" content="{(NOW - timedelta(days=2)).isoformat()}"></head>
<body><article><h1>Acme opens battery plant</h1><p>{ARTICLE_TEXT}</p>
<p>More details about the electric vehicle battery plant follow in this long paragraph to make
trafilatura happy with enough content for extraction of the main text body.</p></article></body></html>"""

PIB_HTML = """<html><body><article><h1>Cabinet approves electric bus scheme</h1>
<p>The Union Cabinet approved a scheme to deploy 10,000 electric buses in cities. The scheme
will be implemented through public transport authorities across states over five years.</p>
</article></body></html>"""


def handler(req: httpx.Request) -> httpx.Response:
    u = str(req.url)
    if "news.google.com/rss/search" in u:
        return httpx.Response(200, text=GNEWS_RSS)
    if "pib.gov.in/RssMain" in u:
        return httpx.Response(200, text=PIB_RSS)
    if "gdeltproject" in u:
        return httpx.Response(200, text="Please limit requests to one every 5 seconds.")
    if "acme.example/news/plant" in u:
        return httpx.Response(200, text=ARTICLE_HTML)
    if "PRID=1" in u:
        return httpx.Response(200, text=PIB_HTML)
    return httpx.Response(404, text="nope")


class FakeDDGS:
    def text(self, q, **kw):
        return []

    def news(self, q, **kw):
        return [{
            "date": (NOW - timedelta(days=2)).isoformat(),
            "title": "Acme opens battery plant in Pune",
            "body": "Acme Motors has opened a new battery plant in Pune.",
            "url": "https://acme.example/news/plant",
            "source": "Acme",
        }]


class BrokenDDGS:
    def news(self, q, **kw):
        raise RuntimeError("rate limited")

    def text(self, q, **kw):
        raise RuntimeError("rate limited")


REQ = ResearchRequest(objective="Indian EV developments", industry="electric vehicle",
                      companies=["Acme Motors"], time_window="1m", source_preferences=["government"])


def make(llm=None, ddgs=FakeDDGS, tmp: Path | None = None) -> OpenResearchProvider:
    return OpenResearchProvider(
        OpenConfig(cache_dir=tmp, company_domains={"acme.example"}),
        transport=httpx.MockTransport(handler),
        ddgs_factory=ddgs,
        llm_call=llm,
        sleep=lambda s: None,
    )


def test_quote_in_text_normalizes() -> None:
    assert quote_in_text("acme motors has opened a NEW battery plant", ARTICLE_TEXT)
    assert not quote_in_text("acme opened a factory on the moon today", ARTICLE_TEXT)
    assert not quote_in_text("short", ARTICLE_TEXT)


def test_categorize() -> None:
    assert categorize("Cabinet approves electric bus scheme") == "policy"
    assert categorize("Acme opens battery plant") == "expansion"


def test_extractive_mode_end_to_end() -> None:
    statuses: list[str] = []
    res = run_research("r1", REQ, make(), status_cb=statuses.append)
    assert statuses[0].startswith("Discovering") and any(s.startswith("Fetching") for s in statuses)
    urls = {s["url"]: s for s in res.sources}
    # old item filtered by window; unrelated PIB item filtered by relevance
    assert not any("articles/old" in u for u in urls)
    assert not any("PRID=2" in u for u in urls)
    pib = urls["https://pib.gov.in/PressReleasePage.aspx?PRID=1"]
    assert pib["source_type"] == "government" and pib["title"]
    acme = urls["https://acme.example/news/plant"]
    assert acme["source_type"] == "company" and acme["published_at"] is not None
    gnews = next(s for s in res.sources if "news.google.com" in s["url"])
    assert gnews["source_type"] == "aggregator" and gnews["domain"] == "Auto News"
    assert all(f["kind"] == "source_excerpt" for f in res.findings)
    plant = next(f for f in res.findings if f["source_ids"] == [acme["id"]])
    assert plant["category"] == "expansion" and plant["entity"] == "Acme Motors"
    assert plant["evidence_quote"] and quote_in_text(ARTICLE_TEXT[:60], plant["evidence_quote"])
    assert res.report["method"] == "extractive"
    assert "GDELT" in " ".join(res.report["coverage_notes"])  # non-JSON body handled
    assert res.report["executive_summary"].startswith(f"{len(res.findings)} developments")


def test_ddgs_failure_does_not_fail_run() -> None:
    res = run_research("r2", REQ, make(ddgs=BrokenDDGS))
    assert res.sources  # Google News + PIB still worked
    assert any("DuckDuckGo" in n for n in res.report["coverage_notes"])


def _llm(findings):
    def call(system: str, user: str) -> str:
        assert "[1]" in user
        return json.dumps({"executive_summary": "EV activity is rising.", "industry_overview": "x",
                           "market_trends": ["trend"], "findings": findings})
    return call


def test_llm_quote_verified_and_rejected() -> None:
    res = run_research("r3", REQ, make(llm=_llm([
        {"title": "Acme plant", "category": "expansion", "sources": [1, 2, 3],
         "evidence_quote": "Acme Motors has opened a new battery plant in Pune"},
        {"title": "Made up", "category": "funding", "sources": [1],
         "evidence_quote": "Acme raised one billion dollars from investors yesterday"},
    ])))
    good, bad = res.findings[:2]
    assert all(f["kind"] == "source_excerpt" for f in res.findings[2:])  # uncited sources kept
    assert good["kind"] == "source_supported" and good["evidence_quote"]
    assert bad["kind"] == "analysis" and "quote_not_found" in bad["flags"] and bad["evidence_quote"] is None
    assert res.report["method"].startswith("llm")
    assert res.report["market_trends"] == ["trend"]


def test_llm_invalid_json_twice_falls_back() -> None:
    calls = {"n": 0}

    def bad(system, user):
        calls["n"] += 1
        return "not json"

    res = run_research("r4", REQ, make(llm=bad))
    assert calls["n"] == 2
    assert res.report["method"] == "extractive"
    assert all(f["kind"] == "source_excerpt" for f in res.findings)


def test_no_sources_raises_readable_error() -> None:
    def empty(req):
        return httpx.Response(404)

    prov = OpenResearchProvider(OpenConfig(), transport=httpx.MockTransport(empty),
                                ddgs_factory=BrokenDDGS, sleep=lambda s: None)
    with pytest.raises(ProviderError) as ei:
        run_research("r5", REQ, prov)
    assert ei.value.code == "no_sources"


def test_cache_avoids_second_fetch(tmp_path: Path) -> None:
    hits = {"n": 0}

    def counting(req):
        hits["n"] += 1
        return handler(req)

    def prov():
        return OpenResearchProvider(OpenConfig(cache_dir=tmp_path), transport=httpx.MockTransport(counting),
                                    ddgs_factory=FakeDDGS, sleep=lambda s: None)

    run_research("a", REQ, prov())
    first = hits["n"]
    run_research("b", REQ, prov())
    assert hits["n"] == first


def test_api_open_provider_without_any_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPETE_DUCKDB_PATH", str(tmp_path / "o.duckdb"))
    monkeypatch.setenv("COMPETE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CONTEXT_DEV_API_KEY", "")
    monkeypatch.setenv("COMPETE_RESEARCH_PROVIDER", "open")
    from fastapi.testclient import TestClient
    from pipeline.config import get_settings
    from pipeline.storage.duckdb_store import Warehouse

    get_settings.cache_clear()
    Warehouse(tmp_path / "o.duckdb").close()
    from api.main import app
    from api.routers import research

    monkeypatch.setattr(research, "provider_factory", lambda *a: make())
    monkeypatch.setattr(research, "_ollama_model", lambda s: None)
    with TestClient(app) as c:
        cfg = c.get("/research/config").json()
        assert cfg["provider"] == "open" and cfg["live_available"] is True
        run = c.post("/research", json={"objective": "Indian EV developments", "time_window": "1m",
                                        "companies": ["Acme Motors"]}).json()
        got = c.get(f"/research/{run['id']}").json()
        assert got["status"] == "completed" and got["provider"] == "open"
        assert got["status_message"] == "Done"
        assert got["result"]["method"] == "extractive"
        srcs = c.get(f"/research/{run['id']}/sources").json()
        assert all(s["discovered_via"] for s in srcs)
        assert c.get("/findings?kind=source_excerpt").json()["total"] >= 1
        # forcing contextdev without a key fails readably, without crashing
        bad = c.post("/research", json={"objective": "Indian EV developments", "provider": "contextdev"}).json()
        assert bad["status"] == "failed" and bad["error_code"] == "missing_key"
    get_settings.cache_clear()


def test_detect_ollama_requires_7b(monkeypatch) -> None:
    from pipeline.research import open_provider as op

    class R:
        def __init__(self, names):
            self._n = names

        def json(self):
            return {"models": [{"name": n} for n in self._n]}

    monkeypatch.setattr(op.httpx, "get", lambda *a, **k: R(["qwen3.5:4b", "nomic-embed-text:latest", "qwen3.5:9b"]))
    assert op.detect_ollama_model("http://x/v1") == "qwen3.5:9b"
    monkeypatch.setattr(op.httpx, "get", lambda *a, **k: R(["qwen3.5:4b"]))
    assert op.detect_ollama_model("http://x/v1") is None


def test_strip_title() -> None:
    from pipeline.research.open_provider import _strip_title

    assert _strip_title("Big News Today\nBody text here.", "Big News Today") == "Body text here."


def test_company_refresh_and_developments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPETE_DUCKDB_PATH", str(tmp_path / "c.duckdb"))
    monkeypatch.setenv("COMPETE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("COMPETE_RESEARCH_PROVIDER", "open")
    from fastapi.testclient import TestClient
    from pipeline.config import get_settings
    from pipeline.storage.duckdb_store import Warehouse

    get_settings.cache_clear()
    wh = Warehouse(tmp_path / "c.duckdb")
    wh.upsert_competitor("acme", "Acme Motors", "acme.example", "EV", 1, "[]")
    wh.close()
    from api.main import app
    from api.routers import research

    monkeypatch.setattr(research, "provider_factory", lambda *a: make())
    monkeypatch.setattr(research, "_ollama_model", lambda s: None)
    with TestClient(app) as c:
        run = c.post("/companies/acme/refresh").json()
        assert run["companies"] == ["Acme Motors"] and run["time_window"] == "1m"
        dev = c.get("/companies/acme/developments").json()
        assert dev and all(not d["is_demo"] for d in dev)
        assert c.post("/companies/nope/refresh").status_code == 404
    get_settings.cache_clear()


def test_cluster_findings_merges_same_story() -> None:
    from pipeline.research.open_provider import cluster_findings

    fs = [
        {"title": "Ola Electric Q2 revenue falls 39%", "source_ids": ["a"], "flags": []},
        {"title": "Ola Electric's Q2 revenue falls by 39%", "source_ids": ["b"], "flags": []},
        {"title": "Ather opens new plant", "source_ids": ["c"], "flags": []},
    ]
    out = cluster_findings(fs)
    assert len(out) == 2 and out[0]["source_ids"] == ["a", "b"] and "multi_source" in out[0]["flags"]


def test_generic_title_detection() -> None:
    from pipeline.research.open_provider import _generic_title

    assert _generic_title("Press Release Page | Press Information Bureau")
    assert _generic_title("Latest Releases - Press Information Bureau")
    assert not _generic_title("Cabinet approves electric bus scheme")


def test_looks_old() -> None:
    from pipeline.research.open_provider import _looks_old

    assert _looks_old("https://archive.pib.gov.in/archive/releases98/lyr2000/rapr2000/r27042000.html", 2026)
    assert _looks_old("https://example.com/news/2019/05/ev.html", 2026)
    assert not _looks_old("https://newindiasamachar.pib.gov.in/WriteReadData/Magazine//2026/Feb/M1.pdf", 2026)
    assert not _looks_old("https://pib.gov.in/PressReleasePage.aspx?PRID=2072136", 2026)


def test_clean_boilerplate() -> None:
    from pipeline.research.open_provider import _lead_sentences

    raw = ("Published OnNov 16, 2026 | 04:50 IST - Last Updated OnNov 16, 2026 | 09:16 IST "
           "Tata Motors PV shares fell 8%. ADVERTISEMENT Analysts cut targets.")
    out = _lead_sentences(raw)
    assert out.startswith("Tata Motors PV shares fell 8%.") and "ADVERTISEMENT" not in out
