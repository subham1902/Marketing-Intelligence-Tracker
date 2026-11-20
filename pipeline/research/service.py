"""Research orchestration: build the provider task, normalize and validate the result.

Pure functions (no DB) so they are easy to test. Persistence lives in
``api/research_store.py``.

Integrity rules enforced here:
* Source titles/snippets only come from the provider (Search API results matched
  by exact URL). Nothing is invented.
* A finding is only marked ``verified_fact`` when at least one of its cited URLs
  appears in the provider's returned ``sources``. Otherwise it is downgraded to
  ``analysis`` and flagged ``unverified_citation``.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from pipeline.research.provider import ProviderError, ResearchProvider

FINDING_CATEGORIES = (
    "expansion",
    "product_launch",
    "partnership",
    "funding",
    "policy",
    "tender",
    "hiring",
    "technology",
    "market_entry",
    "other",
)

_CATEGORY_ALIASES = {
    "manufacturing": "expansion",
    "manufacturing_expansion": "expansion",
    "launch": "product_launch",
    "product": "product_launch",
    "investment": "funding",
    "partnerships": "partnership",
    "regulation": "policy",
    "regulatory": "policy",
    "procurement": "tender",
    "tenders": "tender",
    "market": "market_entry",
}

SOURCE_PREFERENCES = {
    "official_company": "original company announcements, press releases and investor filings",
    "government": "official Indian government sources (e.g. pib.gov.in, heavyindustries.gov.in, morth.nic.in, niti.gov.in)",
    "tenders": "public procurement and tender portals (e.g. gem.gov.in, eprocure.gov.in)",
    "regulatory": "regulators and stock-exchange disclosures (e.g. sebi.gov.in, bseindia.com, nseindia.com)",
    "news": "reputable business news publications",
    "industry": "industry associations and research bodies (e.g. SIAM, SMEV)",
}

_PREF_DOMAINS = {
    "government": ["gov.in", "nic.in"],
    "tenders": ["gem.gov.in", "eprocure.gov.in"],
    "regulatory": ["sebi.gov.in", "bseindia.com", "nseindia.com"],
}

_NEWS_DOMAINS = (
    "economictimes", "livemint", "business-standard", "thehindu", "moneycontrol",
    "reuters", "bloomberg", "financialexpress", "autocarindia", "autocarpro",
    "timesofindia", "hindustantimes", "ndtv", "cnbctv18", "techcrunch", "inc42",
    "yourstory", "evreporter", "rushlane", "thehindubusinessline", "indianexpress",
)

WINDOW_DAYS = {"1m": 30, "3m": 91, "6m": 182, "12m": 365}


def _parse_event_date(s: str | None) -> date | None:
    """Parse YYYY-MM-DD, YYYY-MM or YYYY (end of period, so partial dates are not over-flagged)."""
    if not s:
        return None
    m = re.match(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", s.strip())
    if not m:
        return None
    y, mo, d = int(m.group(1)), m.group(2), m.group(3)
    try:
        if d:
            return date(y, int(mo), int(d))
        if mo:
            mo_i = int(mo)
            return (date(y + (mo_i == 12), mo_i % 12 + 1, 1) - timedelta(days=1))
        return date(y, 12, 31)
    except ValueError:
        return None


TIME_WINDOWS = {
    "1m": "the last month",
    "3m": "the last three months",
    "6m": "the last six months",
    "12m": "the last twelve months",
}

# Example answer object (Context.dev json_format is an example, not a JSON schema).
JSON_FORMAT: dict[str, Any] = {
    "executive_summary": "",
    "industry_overview": "",
    "market_trends": [""],
    "company_developments": [""],
    "product_launches": [""],
    "manufacturing_expansion": [""],
    "partnerships_and_investment": [""],
    "policy_and_regulatory": [""],
    "tenders_and_procurement": [""],
    "commercial_opportunities": [""],
    "risks": [""],
    "findings": [
        {
            "title": "",
            "category": "expansion|product_launch|partnership|funding|policy|tender|hiring|technology|market_entry|other",
            "entity": "",
            "summary": "",
            "significance": 3,
            "confidence": 0.8,
            "kind": "verified_fact|analysis",
            "date": "",
            "source_urls": [""],
        }
    ],
}


@dataclass
class ResearchRequest:
    objective: str
    industry: str | None = None
    geography: str = "India"
    time_window: str = "6m"
    companies: list[str] = field(default_factory=list)
    source_preferences: list[str] = field(default_factory=list)


@dataclass
class NormalizedResult:
    report: dict[str, Any]
    sources: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    partial: bool
    request_id: str | None


def build_task(req: ResearchRequest) -> str:
    window = TIME_WINDOWS.get(req.time_window, "the last six months")
    prefs = [SOURCE_PREFERENCES[p] for p in req.source_preferences if p in SOURCE_PREFERENCES]
    rules = (
        "Rules: only report developments supported by sources you read; put the supporting URLs in "
        "each finding's source_urls; mark kind=verified_fact only for facts stated in a source, "
        "kind=analysis for your inferences; never invent dates, figures or quotes; leave unknown "
        "fields empty. significance is 1-5, confidence 0-1."
    )
    lines = [
        rules,
        f"Research objective: {req.objective.strip()[:1200]}",
        f"Geography: {req.geography}. Time window: {window} (relative to {datetime.now(UTC):%B %Y}).",
    ]
    if req.industry:
        lines.append(f"Industry: {req.industry}.")
    if req.companies:
        lines.append("Companies of interest: " + ", ".join(req.companies[:12]) + ".")
    if prefs:
        lines.append("Prioritize: " + "; ".join(prefs) + ".")
    return "\n".join(lines)[:2000]


def _norm_url(u: str) -> str:
    p = urlparse(u.strip())
    host = (p.netloc or "").lower().removeprefix("www.")
    path = p.path.rstrip("/")
    return f"{host}{path}" + (f"?{p.query}" if p.query else "")


def domain_of(url: str) -> str:
    return (urlparse(url).netloc or "").lower().removeprefix("www.")


def classify_source(url: str, company_domains: set[str] | None = None) -> str:
    d = domain_of(url)
    if any(t in d for t in ("gem.gov.in", "eprocure", "tender")):
        return "tender"
    # Regulators before the generic .gov.in rule, or sebi.gov.in is never "regulatory".
    if any(t in d for t in ("sebi.gov", "bseindia", "nseindia")):
        return "regulatory"
    if d.endswith(".gov.in") or d.endswith(".nic.in") or d == "gov.in":
        return "government"
    if company_domains and any(d == cd or d.endswith("." + cd) for cd in company_domains):
        return "company"
    if any(n in d for n in _NEWS_DOMAINS):
        return "news"
    return "web"


def _item_text(x: Any) -> str:
    if isinstance(x, (str, int, float)):
        return str(x).strip()
    if isinstance(x, dict):  # tolerate object-shaped items: join their scalar values
        vals = [str(v).strip() for v in x.values() if isinstance(v, (str, int, float))]
        return " - ".join(v for v in vals if v)
    return ""


def _str_list(v: Any) -> list[str]:
    if isinstance(v, list):
        return [t for t in (_item_text(x) for x in v) if t]
    if isinstance(v, str) and v.strip():
        return [v.strip()]
    return []


def _clamp_int(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return default


def _clamp_float(v: Any, default: float) -> float:
    try:
        f = float(v)
        if f > 1:  # tolerate 0-100 scale
            f = f / 100
        return max(0.0, min(1.0, f))
    except (TypeError, ValueError):
        return default


def _category(v: Any) -> str:
    s = str(v or "").strip().lower().replace(" ", "_").replace("-", "_")
    if s in FINDING_CATEGORIES:
        return s
    if s in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[s]
    for c in FINDING_CATEGORIES:
        if c in s:
            return c
    return "other"


def _hid(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]


REPORT_SECTIONS = (
    "industry_overview",
    "market_trends",
    "company_developments",
    "product_launches",
    "manufacturing_expansion",
    "partnerships_and_investment",
    "policy_and_regulatory",
    "tenders_and_procurement",
    "commercial_opportunities",
    "risks",
)


def normalize(
    run_id: str,
    content: dict[str, Any],
    source_urls: list[str],
    *,
    industry: str | None,
    search_meta: dict[str, dict[str, Any]] | None = None,
    company_domains: set[str] | None = None,
    partial: bool = False,
    request_id: str | None = None,
    link_status: dict[str, str] | None = None,
    window_start: date | None = None,
) -> NormalizedResult:
    now = datetime.now(UTC)
    search_meta = search_meta or {}
    link_status = link_status or {}

    # ---- sources: provider-returned URLs only, deduped ----
    sources: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for url in source_urls:
        key = _norm_url(url)
        if not key or key in seen:
            continue
        sid = _hid(run_id, key)
        seen[key] = sid
        meta = search_meta.get(key, {})
        sources.append(
            {
                "id": sid,
                "research_run_id": run_id,
                "url": url,
                "domain": domain_of(url),
                "title": meta.get("title"),
                "source_type": classify_source(url, company_domains),
                "published_at": None,  # not provided by the provider API
                "retrieved_at": now,
                "snippet": meta.get("snippet"),
                "link_status": link_status.get(key, "unchecked"),
            }
        )

    # ---- findings: validated against returned sources ----
    findings: list[dict[str, Any]] = []
    raw_findings = content.get("findings") if isinstance(content.get("findings"), list) else []
    for i, f in enumerate(raw_findings):
        if not isinstance(f, dict):
            continue
        title = str(f.get("title") or "").strip()
        summary = str(f.get("summary") or "").strip()
        if not title and not summary:
            continue
        cited = _str_list(f.get("source_urls"))
        matched = [seen[_norm_url(u)] for u in cited if _norm_url(u) in seen]
        unmatched = [u for u in cited if _norm_url(u) not in seen and u.startswith("http")]
        kind = str(f.get("kind") or "analysis").strip().lower()
        kind = "verified_fact" if kind.startswith("verified") or kind == "fact" else "analysis"
        flags: list[str] = []
        if kind == "verified_fact" and not matched:
            kind = "analysis"
            flags.append("unverified_citation")
        # Context.dev appends URLs cited in json_content to `sources`, so presence
        # alone is not proof. If every cited link is unreachable (404/410/DNS),
        # treat the citation as likely fabricated.
        live = [_norm_url(u) for u in cited if _norm_url(u) in seen]
        if live and all(link_status.get(k) == "dead" for k in live):
            kind = "analysis"
            flags.append("dead_citation")
        if not cited:
            flags.append("no_citation")
        # The provider may return older background events; flag (don't hide) them.
        event_date = str(f.get("date") or "").strip() or None
        parsed = _parse_event_date(event_date)
        if window_start and parsed and parsed < window_start:
            flags.append("outside_window")
        findings.append(
            {
                "id": _hid(run_id, str(i), title),
                "research_run_id": run_id,
                "title": title or summary[:90],
                "category": _category(f.get("category")),
                "entity": (str(f.get("entity") or "").strip() or None),
                "industry": industry,
                "summary": summary or None,
                "significance": _clamp_int(f.get("significance"), 1, 5, 3),
                "confidence": _clamp_float(f.get("confidence"), 0.5),
                "kind": kind,
                "event_date": (str(f.get("date") or "").strip() or None),
                "source_ids": matched,
                "cited_urls_unmatched": unmatched,
                "flags": flags,
                "created_at": now,
            }
        )

    report: dict[str, Any] = {
        "executive_summary": str(content.get("executive_summary") or "").strip() or None,
    }
    for key in REPORT_SECTIONS:
        val = content.get(key)
        if key == "industry_overview":
            report[key] = " ".join(_str_list(val)) or None
        else:
            report[key] = _str_list(val)
    return NormalizedResult(report, sources, findings, partial, request_id)


def _search_query(req: ResearchRequest) -> str:
    base = req.industry or req.objective
    q = f"{base} {req.geography}".strip()
    if req.companies:
        q += " " + " OR ".join(req.companies[:4])
    return q[:400]


def _is_tls_error(exc: BaseException) -> bool:
    import ssl

    seen: set[int] = set()
    e: BaseException | None = exc
    while e is not None and id(e) not in seen:
        if isinstance(e, ssl.SSLError):
            return True
        seen.add(id(e))
        e = e.__cause__ or e.__context__
    msg = str(exc).upper()
    return "SSL" in msg or "CERTIFICATE" in msg or "TLS" in msg


def check_links(urls: list[str], *, timeout: float = 8.0, max_urls: int = 40) -> dict[str, str]:
    """Best-effort reachability: ok | dead (404/410/DNS/connect) | unknown (403/429/5xx/timeout)."""
    from concurrent.futures import ThreadPoolExecutor

    import httpx

    def one(url: str) -> tuple[str, str]:
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (market-intel link check)"},
            ) as c:
                r = c.get(url)
            if r.status_code < 400:
                return url, "ok"
            if r.status_code in (404, 410):
                return url, "dead"
            return url, "unknown"
        except httpx.ConnectError as exc:
            # httpcore maps TLS handshake failures to ConnectError too. A bad
            # certificate chain (common on Indian gov sites) is not evidence the
            # page is gone, so only genuine DNS/connection failures count as dead.
            return url, ("unknown" if _is_tls_error(exc) else "dead")
        except Exception:
            return url, "unknown"

    unique = list(dict.fromkeys(urls))[:max_urls]
    if not unique:
        return {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(pool.map(one, unique))
    return {_norm_url(u): st for u, st in results.items()}


def run_research(
    run_id: str,
    req: ResearchRequest,
    provider: ResearchProvider,
    *,
    company_domains: set[str] | None = None,
    link_checker: Any = None,
    status_cb: Any = None,
) -> NormalizedResult:
    """Call the provider and return a validated, normalized result.

    Raises ``ProviderError`` for user-explainable failures.
    """
    # Whole-run providers (the free "open" provider) do discovery, fetching and
    # synthesis themselves and already emit provenance-checked results.
    if hasattr(provider, "research"):
        res = provider.research(run_id, req, status_cb=status_cb)
        ws = (datetime.now(UTC) - timedelta(days=WINDOW_DAYS.get(req.time_window, 182))).date()
        for f in res.findings:
            d = _parse_event_date(f.get("event_date"))
            if d and d < ws and "outside_window" not in f["flags"]:
                f["flags"].append("outside_window")
        return res
    if status_cb:
        status_cb("Waiting for Context.dev answer")
    ans = provider.answer(build_task(req), JSON_FORMAT)
    if not ans.json_content and not ans.sources:
        raise ProviderError("The research provider returned an empty answer.", code="empty")

    # Enrich titles/snippets via Search (non-fatal; exact-URL matching only).
    search_meta: dict[str, dict[str, Any]] = {}
    try:
        domains: list[str] = []
        for p in req.source_preferences:
            domains += _PREF_DOMAINS.get(p, [])
        queries = [(_search_query(req), None)]
        if domains:
            queries.append((_search_query(req), sorted(set(domains))))
        for q, inc in queries:
            res = provider.search(
                q, num_results=20, include_domains=inc, country="in", freshness="last_year"
            )
            for h in res.hits:
                search_meta.setdefault(_norm_url(h.url), {"title": h.title, "snippet": h.snippet})
    except ProviderError:
        pass

    try:
        link_status = (link_checker or check_links)(ans.sources)
    except Exception:
        link_status = {}

    return normalize(
        run_id,
        ans.json_content,
        ans.sources,
        link_status=link_status,
        window_start=(datetime.now(UTC) - timedelta(days=WINDOW_DAYS.get(req.time_window, 182))).date(),
        industry=req.industry,
        search_meta=search_meta,
        company_domains=company_domains,
        partial=ans.partial,
        request_id=ans.request_id,
    )
