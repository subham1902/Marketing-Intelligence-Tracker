"""Marketing Analysis: deterministic extraction, rules, AI validation, endpoints, snapshot. No network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pipeline.marketing import service, signals, synth

ITEMS = [
    {"id": "e1", "url": "https://a.in/1", "domain": "a.in", "title": "Ather Q2 results", "date": "2025-08-01",
     "fetched": True,
     "text": "Ather Energy reported revenue of ₹1,034 crore in FY25, a growth of 20% over the previous year. "
             "Ather Energy faces rivalry from Ola Electric and TVS Motor in the scooter market. "
             "Ather Energy competes with Bajaj Auto and Hero MotoCorp on price and the Ola Electric range. "
             "Ather Energy plans to launch a new platform by 2027 for tier 2 cities. "
             "Ather Energy offered a discount and price cut during the festive campaign. "
             "Ather Energy depends on a supplier of imported cell technology from China."},
    {"id": "e2", "url": "https://b.in/2", "domain": "b.in", "title": "Ather complaints rise", "date": "2023-05-01",
     "fetched": True,
     "text": "Customers raised complaints about Ather Energy service delays and waiting times at the service centre. "
             "Ather Energy faced a subsidy cut that pushed prices higher, a concern for buyers."},
    {"id": "e3", "url": "https://news.google.com/x", "domain": "news.google.com",
     "title": "Ather revenue up 900% to ₹9,999 crore", "date": "2024-01-01", "fetched": False,
     "text": "Ather revenue up 900% to ₹9,999 crore"},
]
CO = service.build_company("ather-energy", "Ather Energy", "EV & Mobility - Two-wheelers")
RIVALS = service.build_rivals([
    {"id": "ather-energy", "name": "Ather Energy", "industry": "EV"},
    {"id": "ola-electric", "name": "Ola Electric", "industry": "EV"},
    {"id": "tvs-motor", "name": "TVS Motor", "industry": "EV"},
])


def test_figures_rupee_crore_and_percent_from_fetched_only() -> None:
    figs = signals.extract_figures(ITEMS, CO["aliases"])
    vals = [f["value"] for f in figs]
    assert any("1,034 crore" in v for v in vals)
    assert any("20%" in v for f in figs for v in f["values"])
    assert not any("9,999" in v for v in vals)  # headline-only figure is never used
    assert figs[0]["period"] == "FY25"


def test_competitor_co_mentions() -> None:
    alias = {k: v["aliases"] for k, v in RIVALS.items() if k != "ather-energy"}
    counts = {c["id"]: c["co_mentions"] for c in signals.competitor_mentions(ITEMS, CO["aliases"], alias)}
    assert counts["ola-electric"] == 2
    assert counts["tvs-motor"] == 1


def test_tone_score() -> None:
    assert signals.tone_score("record growth and strong profit") == 1.0
    assert signals.tone_score("recall and complaints and losses") == -1.0
    assert signals.tone_score("nothing here") == 0.0
    t = signals.tone(ITEMS, CO["aliases"])
    assert t["label"].startswith("Indicative tone from 3")


def test_porter_rules() -> None:
    r = synth.rule_based(CO, ITEMS, RIVALS)
    forces = {p["force"]: p for p in r["porter"]}
    assert forces["Rivalry"]["level"] == "high"  # 4 rivals co-mentioned
    assert forces["Buyer power"]["level"] in ("medium", "high")
    assert forces["Supplier power"]["level"] in ("medium", "high")
    assert forces["Threat of substitutes"]["level"] == "low"
    assert all(p["how"] for p in r["porter"])
    assert len(r) == 13


def test_recommendations_cite_triggers() -> None:
    r = synth.rule_based(CO, ITEMS, RIVALS)
    assert 1 <= len(r["recommendations"]) <= 8
    assert all(x["why"] and x["trigger"] and x["label"] == "Rule-based recommendation"
               for x in r["recommendations"])
    assert any(x["trigger"] == "high_rivalry" for x in r["recommendations"])


def test_ai_rejects_invented_numbers_and_falls_back() -> None:
    claims = [{"claim": "Revenue was ₹1,034 crore", "evidence_ids": ["e1"], "quote": "revenue of ₹1,034 crore"},
              {"claim": "Revenue was ₹5,555 crore", "evidence_ids": ["e1"], "quote": "x"}]
    ok = synth.validate_ai_claims(claims, ITEMS)
    assert len(ok) == 1 and ok[0]["label"] == "AI analysis"
    base = synth.rule_based(CO, ITEMS, RIVALS)
    out, mode = synth.ai_enrich(base, CO, ITEMS, lambda s, u: "not json")
    assert mode == "rule" and out is base

    good = json.dumps({"insights": claims, "recommendations": []})
    out, mode = synth.ai_enrich(base, CO, ITEMS, lambda s, u: good)
    assert mode == "ai" and len(out["ai_insights"]) == 1


# ------------------------------- API + snapshot ---------------------------- #
@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COMPETE_DUCKDB_PATH", str(tmp_path / "m.duckdb"))
    monkeypatch.setenv("COMPETE_DATA_DIR", str(tmp_path))
    from fastapi.testclient import TestClient
    from pipeline.config import get_settings
    from pipeline.storage.duckdb_store import Warehouse

    get_settings.cache_clear()
    Warehouse(tmp_path / "m.duckdb").close()
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps({"analyses": [{
        "id": "mk-snap-ather-energy", "company": "ather-energy", "company_name": "Ather Energy", "mode": "rule",
        "created_at": "2026-11-20T00:00:00+00:00", "result": synth.rule_based(CO, ITEMS, RIVALS),
        "evidence": ITEMS}]}), encoding="utf-8")
    from api import marketing_store
    from api.main import app
    from api.routers import marketing

    monkeypatch.setattr(marketing_store, "SNAPSHOT", snap)
    monkeypatch.setattr(marketing_store.bootstrap, "__defaults__", (snap,))

    class FakeProv:
        synthesis_mode = "extractive"

        def close(self) -> None: ...

    monkeypatch.setattr(marketing, "provider_factory", lambda: FakeProv())
    monkeypatch.setattr(service, "gather", lambda *a, **k: ITEMS)
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_snapshot_loaded_and_endpoints(client) -> None:
    lst = client.get("/api/marketing/analyses?company=ather-energy").json()
    assert lst and lst[0]["is_snapshot"]
    full = client.get(f"/marketing/analyses/{lst[0]['id']}").json()
    assert full["result"]["snapshot"]["evidence_count"] == 3
    r = client.post("/marketing/analyses", json={"name": "Ather Energy"})
    assert r.status_code == 202
    done = client.get(f"/marketing/analyses/{r.json()['id']}").json()
    assert done["status"] == "completed" and done["mode"] == "rule"
    assert client.post("/marketing/analyses", json={}).status_code == 422
    assert client.get("/marketing/analyses/nope").status_code == 404
    h = client.get("/api/health").json()
    assert h["snapshots"]["marketing_analyses"] == 2


def test_ai_recommendations_never_give_investment_advice() -> None:
    base = synth.rule_based(CO, ITEMS, RIVALS)
    payload = json.dumps({
        "insights": [{"claim": "Revenue was ₹1,034 crore", "evidence_ids": ["e1"], "quote": "revenue of ₹1,034 crore"}],
        "recommendations": [
            {"action": "Invest in Ather Energy", "why": "growth", "evidence_ids": ["e1"], "quote": ""},
            {"action": "Buy Ather shares", "why": "growth", "evidence_ids": ["e1"], "quote": ""},
            {"action": "Expand service centres in tier 2 cities", "why": "complaints", "evidence_ids": ["e1"],
             "quote": ""},
        ],
    })
    out, mode = synth.ai_enrich(base, CO, ITEMS, lambda s, u: payload)
    ai = [r["action"] for r in out["recommendations"] if r["label"] == "AI recommendation"]
    assert mode == "ai" and ai == ["Expand service centres in tier 2 cities"]


def test_name_is_cleaned_and_duplicate_runs_are_reused(client, monkeypatch) -> None:
    from api.routers import marketing

    assert marketing._clean("  <b>Bajaj\tAuto</b>\n ") == "Bajaj Auto"
    # Simulate a run still in progress: the second request must reuse it, not start another.
    monkeypatch.setattr(marketing, "process", lambda *a, **k: None)
    first = client.post("/marketing/analyses", json={"name": "Hero MotoCorp"}).json()
    second = client.post("/marketing/analyses", json={"name": "  Hero   MotoCorp "}).json()
    assert first["id"] == second["id"] and first["status"] == "queued"
    for n in ("A Co", "B Co"):
        client.post("/marketing/analyses", json={"name": n})
    assert client.post("/marketing/analyses", json={"name": "D Co"}).status_code == 429
