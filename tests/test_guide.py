"""In-app guide tests (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.assistant import guide

QUESTIONS = {
    "where do I run research?": "nav-research",
    "what does Source excerpt mean?": "concept-source-excerpt",
    "how do I refresh a company's news?": "howto-refresh-news",
    "how can I hide the demo snapshot": "howto-hide-demo",
    "what is quote verified": "concept-source-supported",
    "why does the date say not available": "concept-date-na",
    "how do I connect an api key for openai": "howto-connect-llm",
    "my research failed, why?": "trouble-failed",
    "what is ctrl+k": "nav-palette",
    "what does this app do": "about-product",
}


@pytest.mark.parametrize("q,expected", list(QUESTIONS.items()))
def test_retrieval_picks_right_entry(q: str, expected: str) -> None:
    top = guide.retrieve(q, None, k=1)[0][0]
    assert top.id == expected, (q, top.id)


def test_pathname_boost() -> None:
    plain = dict((e.id, s) for e, s in guide.retrieve("filter", None, k=40))
    boosted = dict((e.id, s) for e, s in guide.retrieve("filter", "/feed", k=40))
    assert boosted["howto-filter-feed"] > plain["howto-filter-feed"]


def test_low_confidence_is_honest() -> None:
    r = guide.kb_reply("what's the weather in paris tomorrow", "/dashboard")
    assert not r.confident and r.kind == "low_confidence" and len(r.suggestions) == 3
    assert "not sure" in r.text


def test_intents_and_status_reply() -> None:
    assert guide.intent("what's the status of my research?") == "status"
    assert guide.intent("what just happened?") == "activity"
    assert guide.intent("how many companies am I tracking") == "count"
    r = guide.status_reply([{"id": "rr-1", "status": "running", "status_message": "Fetching 25 sources",
                             "objective": "Ola news", "is_demo": False}])
    assert "1 run is in progress" in r.text and "Fetching 25 sources" in r.text
    assert r.actions[0]["route"] == "/research/view?id=rr-1"


def test_activity_reply_mentions_failure() -> None:
    r = guide.activity_reply([
        {"label": "Loaded intelligence feed", "status": "success", "durationMs": 300},
        {"label": "Started a research run", "status": "error", "error": "Request failed (500)"},
    ])
    assert "failed" in r.text and "Started a research run" in r.text


def test_trailer_parses() -> None:
    r = guide.GuideReply("Hello there", [{"label": "Open Feed", "route": "/feed"}], ["a", "b", "c"], ["nav-feed"])
    body = "".join(guide.word_chunks(r.text)) + guide.meta_line(r)
    text, meta = guide.parse_stream(body)
    assert text == "Hello there" and meta["actions"][0]["route"] == "/feed" and len(meta["suggestions"]) == 3


def test_chat_route_streams_and_reads_duckdb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPETE_DUCKDB_PATH", str(tmp_path / "g.duckdb"))
    monkeypatch.setenv("COMPETE_DATA_DIR", str(tmp_path))
    from fastapi.testclient import TestClient
    from pipeline.config import get_settings
    from pipeline.storage.duckdb_store import Warehouse

    get_settings.cache_clear()
    wh = Warehouse(tmp_path / "g.duckdb")
    wh.upsert_competitor("acme", "Acme", "acme.in", "EV", 1, "[]")
    wh.close()
    from api.main import app

    with TestClient(app) as c:
        with c.stream("POST", "/api/assistant/chat",
                      json={"message": "how many companies do I track?", "pathname": "/dashboard"}) as r:
            assert r.status_code == 200
            body = "".join(r.iter_text())
        text, meta = guide.parse_stream(body)
        assert "1 companies" in text and meta["actions"][0]["route"] == "/competitors"
        r2 = c.post("/assistant/chat", json={"message": "where do I run research?", "pathname": "/dashboard"})
        text2, meta2 = guide.parse_stream(r2.text)
        assert "Run research" in text2 and meta2["sources"][0] == "nav-research"
        st = c.get("/api/assistant/starters", params={"pathname": "/research"}).json()
        assert st["page"] == "Research" and len(st["starters"]) == 3
    get_settings.cache_clear()
