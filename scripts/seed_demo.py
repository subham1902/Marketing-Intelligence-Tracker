"""Seed the warehouse with curated, realistic demo data.

Makes the API and dashboard fully demoable without any API key or pipeline run.
Populates the raw layer (competitors, signals, changes, jobs snapshots, llm
calls, reports) with hand-authored data, then (optionally) runs ``dbt build`` to
materialize the marts.

Usage:
    uv run python scripts/seed_demo.py            # seed raw only
    uv run python scripts/seed_demo.py --build    # seed + dbt build
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta

from pipeline.config import REPO_ROOT, get_settings
from pipeline.extract.embeddings import HashingEmbedder
from pipeline.logging_setup import get_logger
from pipeline.schemas import RawPage, SourceType
from pipeline.storage.duckdb_store import Warehouse

log = get_logger("seed")
EMB = HashingEmbedder(256)
NOW = datetime.now(UTC)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:24]


def _ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


# ---------------------------------------------------------------------------
# DEMO SNAPSHOT - Indian EV & mobility.
# Every record below is SAMPLE data for offline demos. Titles carry a
# "[Sample]" prefix and signals point only at the company's real home page
# (never a fabricated article URL), so nothing here can be mistaken for live
# intelligence. Live findings come from the Research workspace (Context.dev)
# with real source links.
# ---------------------------------------------------------------------------
DEMO_INDUSTRY = "EV & Mobility (India)"

COMPETITORS = [
    ("tata-motors", "Tata Motors", "tatamotors.com", "EV & Mobility - Passenger & Commercial", 1),
    ("mahindra", "Mahindra", "mahindra.com", "EV & Mobility - Passenger & Commercial", 1),
    ("tvs-motor", "TVS Motor", "tvsmotor.com", "EV & Mobility - Two/Three-wheelers", 1),
    ("ather-energy", "Ather Energy", "atherenergy.com", "EV & Mobility - Two-wheelers", 1),
    ("ola-electric", "Ola Electric", "olaelectric.com", "EV & Mobility - Two-wheelers", 1),
    ("exide", "Exide Industries", "exideindustries.com", "EV & Mobility - Batteries", 2),
    ("amara-raja", "Amara Raja Energy & Mobility", "amararajaeandm.com", "EV & Mobility - Batteries", 2),
]

TRACKED = {
    "tata-motors": [("https://www.tatamotors.com/", "static", "press_release")],
    "mahindra": [("https://www.mahindra.com/", "static", "press_release")],
    "tvs-motor": [("https://www.tvsmotor.com/", "static", "product_launch")],
    "ather-energy": [("https://www.atherenergy.com/", "dynamic", "product_launch")],
    "ola-electric": [("https://www.olaelectric.com/", "dynamic", "product_launch")],
    "exide": [("https://www.exideindustries.com/", "static", "press_release")],
    "amara-raja": [("https://www.amararajaeandm.com/", "static", "press_release")],
}

# (days_ago, signal_type, title, summary, significance) - illustrative only.
CONTENT = {
    "tata-motors": [
        (3, "product_launch", "[Sample] New EV variant listed on website",
         "Illustrative demo signal: a new electric variant page appeared on the tracked site.", 4),
        (17, "press_release", "[Sample] Charging partnership announcement",
         "Illustrative demo signal: a press page mentions a charging-network partnership.", 3),
    ],
    "mahindra": [
        (5, "product_launch", "[Sample] Electric SUV booking page update",
         "Illustrative demo signal: booking details changed on an electric SUV page.", 4),
        (26, "funding_news", "[Sample] EV subsidiary investment note",
         "Illustrative demo signal: investor material references EV-unit capital allocation.", 4),
    ],
    "tvs-motor": [
        (4, "product_launch", "[Sample] Electric scooter range refresh",
         "Illustrative demo signal: the specification table for an electric scooter was updated.", 3),
        (21, "press_release", "[Sample] Export market expansion",
         "Illustrative demo signal: a press page lists new export markets for EV models.", 3),
    ],
    "ather-energy": [
        (2, "product_launch", "[Sample] Software update for scooter lineup",
         "Illustrative demo signal: a release-notes page lists new connected features.", 3),
        (14, "press_release", "[Sample] New experience centres",
         "Illustrative demo signal: the store-locator count increased across Tier-2 cities.", 2),
    ],
    "ola-electric": [
        (6, "product_launch", "[Sample] Cell manufacturing page update",
         "Illustrative demo signal: a page on in-house cell manufacturing was revised.", 4),
        (30, "leadership_change", "[Sample] Leadership page change",
         "Illustrative demo signal: the leadership page added a new executive.", 3),
    ],
    "exide": [
        (9, "press_release", "[Sample] Lithium-ion cell plant progress",
         "Illustrative demo signal: an investor page mentions lithium-ion cell plant milestones.", 4),
    ],
    "amara-raja": [
        (12, "press_release", "[Sample] Cell giga-factory project update",
         "Illustrative demo signal: a project update on advanced-chemistry cell capacity.", 4),
    ],
}

# (days_ago, plan, price_inr) - sample ex-showroom prices for the pricing chart.
PRICING = {
    "ather-energy": [(60, "Pro", 145000), (20, "Pro", 139999), (20, "Plus", 119999)],
    "ola-electric": [(55, "Pro", 139999), (25, "Pro", 129999), (10, "Plus", 99999)],
    "tvs-motor": [(45, "Premium", 125000), (15, "Premium", 122000)],
}

# (role, location, days_ago) - sample hiring snapshots.
JOBS = {
    "tata-motors": [
        ("Battery Systems Engineer", "Pune, India", 3),
        ("EV Charging Partnerships Manager", "Mumbai, India", 10),
    ],
    "mahindra": [("Electric Powertrain Lead", "Chennai, India", 5)],
    "tvs-motor": [("BMS Firmware Engineer", "Hosur, India", 4)],
    "ather-energy": [
        ("Embedded Software Engineer", "Bengaluru, India", 2),
        ("Retail Expansion Manager", "Bengaluru, India", 15),
    ],
    "ola-electric": [("Cell Chemistry Scientist", "Krishnagiri, India", 6)],
    "exide": [("Li-ion Process Engineer", "Bengaluru, India", 9)],
    "amara-raja": [("Cell Manufacturing Engineer", "Telangana, India", 11)],
}

# Demo research snapshot (is_demo = true). Sources are real, generic portal /
# home pages - NOT citations for specific claims - and every finding is
# labelled analysis, never verified fact.
DEMO_RESEARCH_OBJECTIVE = (
    "[Demo snapshot] India electric mobility landscape: competitor developments, policy, "
    "procurement and commercial opportunities."
)
DEMO_RESEARCH_SOURCES = [
    ("https://heavyindustries.gov.in/", "government"),
    ("https://pib.gov.in/", "government"),
    ("https://gem.gov.in/", "tender"),
    ("https://www.tatamotors.com/", "company"),
    ("https://www.atherenergy.com/", "company"),
    ("https://www.olaelectric.com/", "company"),
]
DEMO_RESEARCH_FINDINGS = [
    ("[Sample] Two-wheelers drive EV unit volumes", "market_entry", None,
     "Demo snapshot: illustrative analysis that electric two-wheelers are the largest EV segment by units.", 4),
    ("[Sample] Domestic cell manufacturing build-out", "expansion", "Battery makers",
     "Demo snapshot: illustrative analysis of battery companies investing in local cell capacity.", 4),
    ("[Sample] Incentive scheme changes affect pricing", "policy", "Government of India",
     "Demo snapshot: illustrative analysis that demand-incentive revisions influence retail pricing.", 4),
    ("[Sample] Public procurement of electric buses", "tender", "State transport undertakings",
     "Demo snapshot: illustrative example of procurement opportunities for electric buses.", 3),
    ("[Sample] OEM and charging-network tie-ups", "partnership", "OEMs",
     "Demo snapshot: illustrative analysis of OEMs partnering with charging operators.", 3),
    ("[Sample] Connected software as a differentiator", "technology", "Two-wheeler OEMs",
     "Demo snapshot: illustrative analysis of competition on connected features.", 2),
    ("[Sample] Hiring demand in battery engineering", "hiring", None,
     "Demo snapshot: illustrative analysis of hiring demand for BMS and cell engineers.", 2),
]
DEMO_RESEARCH_REPORT = {
    "executive_summary": (
        "DEMO SNAPSHOT - sample content for offline demonstration, not live research. "
        "Configure CONTEXT_DEV_API_KEY and run a research objective to generate a "
        "source-linked report."
    ),
    "industry_overview": (
        "Sample overview: India's EV market spans two-wheelers, three-wheelers, passenger "
        "cars, buses and the battery supply chain."
    ),
    "market_trends": ["[Sample] Electrification led by two- and three-wheelers."],
    "company_developments": ["[Sample] OEMs expanding EV portfolios and retail reach."],
    "product_launches": ["[Sample] Frequent variant refreshes in electric scooters."],
    "manufacturing_expansion": ["[Sample] Investment in domestic cell manufacturing."],
    "partnerships_and_investment": ["[Sample] OEM-charging operator partnerships."],
    "policy_and_regulatory": ["[Sample] Central and state incentive schemes shape demand."],
    "tenders_and_procurement": ["[Sample] Public e-bus procurement creates B2G openings."],
    "commercial_opportunities": ["[Sample] Fleet electrification and battery recycling."],
    "risks": ["[Sample] Incentive changes, cell import dependence and price competition."],
}


def seed_demo_research(db_path) -> int:
    """Insert (or refresh) the clearly-labelled demo research snapshot.

    Live research runs already in the warehouse are preserved.
    """
    from api import research_store as rstore
    from api.db import ApiDB

    db = ApiDB(db_path)
    try:
        rstore.bootstrap(db)
        old = db.query("SELECT id FROM research.research_runs WHERE is_demo")
        for r in old:
            db.execute("DELETE FROM research.research_sources WHERE research_run_id=?", [r["id"]])
            db.execute("DELETE FROM research.research_findings WHERE research_run_id=?", [r["id"]])
            db.execute("DELETE FROM research.research_runs WHERE id=?", [r["id"]])
        run_id = "demo-ev-india"
        created = _ago(1)
        rstore.create_run(
            db,
            {
                "id": run_id,
                "objective": DEMO_RESEARCH_OBJECTIVE,
                "industry": DEMO_INDUSTRY,
                "geography": "India",
                "time_window": "6m",
                "date_from": _ago(182).date(),
                "date_to": NOW.date(),
                "companies": [c[1] for c in COMPETITORS],
                "source_preferences": ["official_company", "government", "tenders"],
                "status": "queued",
                "provider": "demo",
                "is_demo": True,
                "created_at": created,
            },
        )
        sources = []
        for url, stype in DEMO_RESEARCH_SOURCES:
            sources.append(
                {
                    "id": _hash(f"{run_id}:{url}"),
                    "url": url,
                    "domain": url.split("//", 1)[1].split("/", 1)[0].removeprefix("www."),
                    "title": None,
                    "source_type": stype,
                    "published_at": None,
                    "retrieved_at": None,
                    "snippet": "Demo snapshot: generic portal/home page, not a citation for a specific claim.",
                }
            )
        findings = []
        for title, cat, entity, summary, sig in DEMO_RESEARCH_FINDINGS:
            findings.append(
                {
                    "id": _hash(f"{run_id}:{title}"),
                    "title": title,
                    "category": cat,
                    "entity": entity,
                    "industry": DEMO_INDUSTRY,
                    "summary": summary,
                    "significance": sig,
                    "confidence": 0.5,
                    "kind": "analysis",
                    "event_date": None,
                    "source_ids": [],
                    "flags": ["demo"],
                    "created_at": created,
                }
            )
        rstore.complete_run(
            db,
            run_id,
            report=DEMO_RESEARCH_REPORT,
            sources=sources,
            findings=findings,
            partial=False,
            request_id=None,
            completed_at=created,
        )
        return 1
    finally:
        db.close()


def _wipe(wh: Warehouse) -> None:
    for table in ("signals", "changes", "llm_calls", "reports", "raw_pages", "competitors"):
        wh.conn.execute(f"DELETE FROM raw.{table}")


def _store_signal_and_change(
    wh: Warehouse,
    comp_id: str,
    domain: str,
    when: datetime,
    signal_type: str,
    title: str,
    summary: str,
    significance: int,
) -> int:
    url = TRACKED[comp_id][0][0] if TRACKED.get(comp_id) else None
    source_hash = _hash(f"{comp_id}:{title}:{when.isoformat()}")
    sid = _hash(f"{comp_id}:{title}:{source_hash}")
    wh.upsert_signal(
        signal_id=sid,
        competitor_id=comp_id,
        url=url,
        signal_type=signal_type,
        title=title,
        summary=summary,
        entities_json=json.dumps(_entities(title)),
        significance=significance,
        confidence=0.85,
        embedding=EMB.embed_one(f"{title} {summary}"),
        source_hash=source_hash,
        model="seed",
        extracted_at=when,
    )
    wh.insert_change(
        change_id=f"chg-{sid}",
        competitor_id=comp_id,
        url=url,
        signal_type=signal_type,
        change_type="new",
        summary=summary,
        significance_score=significance,
        prev_hash=None,
        new_hash=source_hash,
        detected_at=when,
    )
    return significance


def _entities(title: str) -> list[str]:
    return re.findall(r"[A-Z][A-Za-z0-9.+]+(?:\s[A-Z0-9][A-Za-z0-9.+]*){0,2}", title)[:4]


def seed(wh: Warehouse) -> dict[str, int]:
    _wipe(wh)
    counts = {"competitors": 0, "signals": 0, "changes": 0, "jobs": 0, "reports": 0}

    for cid, name, domain, industry, tier in COMPETITORS:
        tracked = [
            {"url": u, "source_type": st, "signal_hint": sh} for u, st, sh in TRACKED.get(cid, [])
        ]
        wh.upsert_competitor(cid, name, domain, industry, tier, json.dumps(tracked))
        counts["competitors"] += 1

        for days, st, title, summary, sig in CONTENT.get(cid, []):
            _store_signal_and_change(wh, cid, domain, _ago(days), st, title, summary, sig)
            counts["signals"] += 1
            counts["changes"] += 1

        for days, plan, price in PRICING.get(cid, []):
            title = f"[Sample] {plan} variant price update"
            summary = f"[Sample] The {plan} variant is listed at ₹{price:,} ex-showroom."
            _store_signal_and_change(
                wh, cid, domain, _ago(days), "pricing_change", title, summary, 3
            )
            counts["signals"] += 1
            counts["changes"] += 1

        for role, location, days in JOBS.get(cid, []):
            when = _ago(days)
            body = f"{role} ({location})\n\nWe are hiring a {role} based in {location}."
            chash = _hash(f"{cid}:{role}:{location}")
            wh.upsert_raw_page(
                RawPage(
                    id=_hash(f"jobs:{cid}:{role}"),
                    competitor_id=cid,
                    url=f"https://www.{domain}/#careers-{_slug(role)}",
                    source_type=SourceType.JOBS,
                    raw_html=body,
                    clean_text=body,
                    http_status=200,
                    content_hash=chash,
                    fetched_at=when,
                )
            )
            counts["jobs"] += 1

    # A few LLM call logs for cost display.
    for i in range(12):
        wh.log_llm_call(
            call_id=f"seed-call-{i}",
            ts=_ago(i),
            provider="mock",
            model="seed",
            url="https://example.com",
            prompt_tokens=1200,
            completion_tokens=180,
            total_tokens=1380,
            latency_ms=900,
            ok=True,
            error=None,
        )

    # Two demo weekly reports.
    for wk, title in [(7, "[Demo] Weekly EV Competitive Brief"), (14, "[Demo] Weekly EV Competitive Brief")]:
        week_start = (_ago(wk)).date()
        body = (
            f"# {title} - week of {week_start}\n\n"
            "> DEMO SNAPSHOT - sample report generated from the seeded [Sample] signals. "
            "Not live market intelligence.\n\n"
            "## Executive summary\n"
            "Sample week: EV variant updates from two-wheeler OEMs, battery makers signalling "
            "cell-manufacturing progress, and steady hiring in battery engineering.\n\n"
            "## Top changes (sample)\n"
            "1. **Tata Motors - [Sample] New EV variant listed** (significance 4)\n"
            "2. **Ola Electric - [Sample] Cell manufacturing page update** (significance 4)\n"
            "3. **Ather Energy - [Sample] Pro variant price update** (significance 3)\n\n"
            "## What to watch\n"
            "- Domestic cell capacity (Exide, Amara Raja).\n"
            "- Use the Research workspace for live, source-linked findings.\n"
        )
        wh.upsert_report(
            report_id=f"report-{week_start}",
            title=f"{title} - {week_start}",
            week_start=week_start,
            summary="Sample data: EV variant updates, cell-manufacturing signals, battery hiring.",
            body_md=body,
            created_at=_ago(wk - 0.2),
        )
        counts["reports"] += 1

    return counts


def run_dbt_build() -> bool:
    import os

    from dbt.cli.main import dbtRunner

    os.environ["COMPETE_DUCKDB_PATH"] = str(get_settings().duckdb_path)
    proj = str(REPO_ROOT / "warehouse" / "dbt")
    res = dbtRunner().invoke(["build", "--project-dir", proj, "--profiles-dir", proj])
    return bool(res.success)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data into the warehouse.")
    parser.add_argument("--build", action="store_true", help="Run dbt build after seeding.")
    args = parser.parse_args()

    settings = get_settings()
    settings.ensure_dirs()
    wh = Warehouse.from_settings(settings)
    counts = seed(wh)
    wh.close()
    counts["research_runs"] = seed_demo_research(settings.duckdb_path)
    log.info("seeded: %s", counts)
    print("Seeded demo data:", counts)

    if args.build:
        ok = run_dbt_build()
        print("dbt build:", "OK" if ok else "FAILED")
        if not ok:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
