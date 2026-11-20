"""Free evidence gathering for a Marketing Analysis (reuses the open research provider)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pipeline.research.open_provider import (
    Candidate,
    OpenResearchProvider,
    _hid,
    _norm_url,
    host_of,
)

QUERY_TEMPLATES = [
    "{co} revenue profit FY", "{co} market share", "{co} competitors", "{co} customers target segment",
    "{co} pricing", "{co} dealership OR distribution OR stores", "{co} marketing campaign",
    "{co} launch plans", "{co} complaints OR recall OR reviews", "{co} partnership",
    "{co} government policy subsidy", "{co} suppliers", "{co} investors",
]


def queries(name: str, now: datetime | None = None) -> list[str]:
    y = (now or datetime.now(UTC)).year
    qs = [t.format(co=name) for t in QUERY_TEMPLATES]
    qs += [f"{name} strategy {y - 2}", f"{name} results {y - 3}"]  # past, time-scoped via query text
    return list(dict.fromkeys(qs))


def _to_item(c: Candidate) -> dict[str, Any]:
    fetched = bool(c.text)
    return {
        "id": "ev-" + _hid(_norm_url(c.url))[:10], "url": c.url, "domain": host_of(c.url),
        "title": c.title, "date": c.published_at.date().isoformat() if c.published_at else None,
        "text": (c.text or c.snippet or c.title or "")[:12000], "fetched": fetched,
        "via": c.via, "aggregator": c.aggregator,
    }


def gather(provider: OpenResearchProvider, name: str, *, max_pages: int = 30,
           status_cb: Callable[[str], None] | None = None) -> list[dict[str, Any]]:
    cb = status_cb or (lambda _s: None)
    cb("Gathering evidence")
    cands: list[Candidate] = []
    for q in queries(name):
        cands += provider._ddgs_news(q, 365)
        if len(cands) < 60:
            cands += provider._google_news(q, 1100)
    seen: set[str] = set()
    picked: list[Candidate] = []
    key_name = name.lower().split()[0]
    for c in sorted(cands, key=lambda c: (c.aggregator, -(c.published_at.timestamp() if c.published_at else 0))):
        k = _norm_url(c.url)
        blob = f"{c.title or ''} {c.snippet or ''}".lower()
        if k in seen or key_name not in blob:
            continue
        seen.add(k)
        picked.append(c)
        if len(picked) >= max_pages:
            break
    cb(f"Reading {len(picked)} sources")
    provider.fetch(picked)
    return [_to_item(c) for c in picked if (c.text or c.snippet or c.title)]
