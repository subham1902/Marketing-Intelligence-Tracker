"""Free, keyless "open" research provider.

Implements the ``ResearchProvider`` protocol plus a ``research()`` method that
``service.run_research`` prefers when present. Pipeline:

1. **Discover** (all free, no key; every source optional and failure-tolerant):
   DuckDuckGo news via ``ddgs``, Google News RSS, PIB official press-release RSS,
   GDELT DOC 2.0. Raw responses are cached under ``data/research_cache/``.
2. **Fetch + extract** each candidate with httpx + trafilatura (title, real
   snippet, publish date from page metadata when available).
3. **Synthesize**:
   * LLM mode (local Ollama): findings must quote evidence copied from a cited
     source; the quote is verified in code (``source_supported``) or the finding
     is downgraded to ``analysis`` with flag ``quote_not_found``.
   * Extractive mode (no LLM): each relevant article becomes a ``source_excerpt``
     finding whose summary is verbatim source text. No invented prose.

Provenance rules: nothing is fabricated - unknown dates/titles stay ``None``.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx

from pipeline.logging_setup import get_logger
from pipeline.research.provider import AnswerResult, ProviderError, SearchResult

log = get_logger(__name__)

UA = "Mozilla/5.0 (compatible; market-intel-tracker/0.1; +https://github.com/yassnemo/compete)"
MAX_SOURCES = 25
EXCERPT_CHARS = 700

StatusCb = Callable[[str], None]

# Category keyword rules (adapted from the mock extractor's keyword approach).
_CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("tender", ("tender", "procurement", "bid ", "bids ", "rfp", "gem portal", "e-procurement")),
    ("policy", ("scheme", "policy", "ministry", "government", "subsidy", "incentive", "pli",
                "fame", "pm e-drive", "regulation", "notification", "gst", "cabinet")),
    ("funding", ("funding", "raises", "raised", "investment", "invest", "ipo", "stake",
                 "crore fund", "series ", "valuation")),
    ("partnership", ("partner", "partnership", "tie-up", "ties up", "collaborat", "mou",
                     "joint venture", "alliance", "agreement")),
    ("expansion", ("plant", "factory", "capacity", "facility", "manufacturing", "expand",
                   "expansion", "gigafactory", "production")),
    ("product_launch", ("launch", "unveil", "introduce", "new model", "variant", "debut",
                        "rolls out", "launched")),
    ("hiring", ("hiring", "appoint", "ceo", "cfo", "chief ", "executive", "layoff", "jobs")),
    ("technology", ("battery", "cell", "software", "charging technology", "technology", "r&d")),
    ("market_entry", ("enters", "entry", "export", "market share", "sales", "registrations")),
]

_SECTION_FOR_CATEGORY = {
    "product_launch": "product_launches",
    "expansion": "manufacturing_expansion",
    "partnership": "partnerships_and_investment",
    "funding": "partnerships_and_investment",
    "policy": "policy_and_regulatory",
    "tender": "tenders_and_procurement",
}

_WINDOW_DAYS = {"1m": 30, "3m": 91, "6m": 182, "12m": 365}


# ------------------------------------------------------------------ helpers --
def _norm_url(u: str) -> str:
    from pipeline.research.service import _norm_url as n

    return n(u)


def _hid(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]


def _norm_text(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[‐-―]", "-", s)
    return re.sub(r"\s+", " ", s).strip()


def quote_in_text(quote: str, text: str) -> bool:
    """True if ``quote`` (>= 20 chars after normalization) occurs verbatim in ``text``."""
    q = _norm_text(quote or "").strip(" .\"'")
    return len(q) >= 20 and q in _norm_text(text or "")


def _parse_dt(v: Any) -> datetime | None:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    s = str(v).strip()
    with contextlib.suppress(Exception):
        return parsedate_to_datetime(s)  # RFC 822 (RSS)
    m = re.match(r"^(\d{8})T(\d{6})Z$", s)  # GDELT seendate
    if m:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    with contextlib.suppress(ValueError):
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    return None


def _lead_sentences(text: str, n: int = 2, max_chars: int = 400) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = " ".join(parts[:n]).strip()
    return out[:max_chars].rsplit(" ", 1)[0] + "…" if len(out) > max_chars else out


def categorize(text: str) -> str:
    t = (text or "").lower()
    for cat, kws in _CATEGORY_RULES:
        if any(k in t for k in kws):
            return cat
    return "other"


def _strip_title(text: str, title: str | None) -> str:
    """Drop a leading copy of the headline that trafilatura keeps in the body."""
    t = (text or "").lstrip()
    if title:
        head = title.strip()
        if t[: len(head)].lower() == head.lower():
            t = t[len(head):].lstrip(" :-\n")
    return t


_STOP = {"the", "a", "an", "of", "in", "on", "for", "to", "and", "with", "as", "by", "at", "its", "is", "from"}


def _tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (title or "").lower()) if w not in _STOP and len(w) > 2}


def cluster_findings(findings: list[dict[str, Any]], threshold: float = 0.6) -> list[dict[str, Any]]:
    """Merge findings whose headlines describe the same story (token Jaccard >= threshold).

    The first (highest-ranked) finding is kept; the others' sources are attached
    and the finding is flagged ``multi_source`` so the UI can show "N sources".
    """
    out: list[dict[str, Any]] = []
    toks: list[set[str]] = []
    for f in findings:
        t = _tokens(f["title"])
        for i, kept in enumerate(out):
            u = t | toks[i]
            if u and len(t & toks[i]) / len(u) >= threshold:
                for sid in f["source_ids"]:
                    if sid not in kept["source_ids"]:
                        kept["source_ids"].append(sid)
                if "multi_source" not in kept["flags"]:
                    kept["flags"].append("multi_source")
                break
        else:
            out.append(f)
            toks.append(t)
    return out


_GENERIC_TITLE = re.compile(
    r"^(press release page|latest releases|press information bureau|home|news|press releases?)"
    r"(\s*[|\-:]\s*(press information bureau|pib|government of india))*\s*$",
    re.IGNORECASE,
)


def _generic_title(t: str | None) -> bool:
    return bool(t) and bool(_GENERIC_TITLE.match(t.strip()))


def _english(s: str) -> bool:
    return bool(s) and sum(c.isascii() for c in s) / len(s) > 0.9


@dataclass
class Candidate:
    url: str
    title: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    snippet: str | None = None
    via: str = ""
    aggregator: bool = False
    text: str | None = None
    date_label: str | None = None  # e.g. "first seen by GDELT"


@dataclass
class OpenConfig:
    cache_dir: Path | None = None
    llm_model: str | None = None  # Ollama model name, or None for extractive mode
    ollama_base_url: str = "http://localhost:11434/v1"
    fetch_pages: bool = True
    throttle_seconds: float = 1.0
    gdelt_throttle_seconds: float = 5.0
    company_domains: set[str] = field(default_factory=set)


# ----------------------------------------------------------------- provider --
class OpenResearchProvider:
    name = "open"

    def __init__(
        self,
        config: OpenConfig | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        ddgs_factory: Callable[[], Any] | None = None,
        llm_call: Callable[[str, str], str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cfg = config or OpenConfig()
        self._http = httpx.Client(
            headers={"User-Agent": UA}, timeout=httpx.Timeout(15, connect=8),
            follow_redirects=True, transport=transport,
        )
        self._ddgs_factory = ddgs_factory if ddgs_factory is not None else _default_ddgs
        self._llm_call = llm_call
        self._sleep = sleep
        self.notes: list[str] = []
        self.synthesis_mode = "llm" if (llm_call or self.cfg.llm_model) else "extractive"

    def close(self) -> None:
        self._http.close()

    # Protocol compatibility: the open provider does whole-run research instead.
    def answer(self, task: str, json_format: dict[str, Any]) -> AnswerResult:
        raise ProviderError("Use research() for the open provider.", code="unsupported")

    def search(self, query: str, **_: Any) -> SearchResult:
        return SearchResult()

    # ------------------------------------------------------------- caching --
    def _cache_get(self, key: str) -> Any | None:
        if not self.cfg.cache_dir:
            return None
        p = self.cfg.cache_dir / f"{_hid(key)}.json"
        if p.exists() and time.time() - p.stat().st_mtime < 6 * 3600:
            with contextlib.suppress(Exception):
                return json.loads(p.read_text(encoding="utf-8"))
        return None

    def _cache_put(self, key: str, value: Any) -> None:
        if not self.cfg.cache_dir:
            return
        with contextlib.suppress(Exception):
            self.cfg.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cfg.cache_dir / f"{_hid(key)}.json").write_text(
                json.dumps(value, default=str), encoding="utf-8"
            )

    def _get_text(self, url: str, *, throttle: float | None = None) -> tuple[int, str]:
        cached = self._cache_get("GET " + url)
        if cached is not None:
            return int(cached[0]), str(cached[1])
        self._sleep(self.cfg.throttle_seconds if throttle is None else throttle)
        r = self._http.get(url)
        self._cache_put("GET " + url, [r.status_code, r.text])
        return r.status_code, r.text

    # ----------------------------------------------------------- discovery --
    def _queries(self, req: Any) -> list[str]:
        base = (req.industry or "electric vehicle").strip()
        geo = req.geography or "India"
        # The objective's own words lead: a short objective ("Ola Electric developments")
        # is usually the most specific query we have.
        stop = {"research", "identify", "the", "and", "of", "in", "for", "over", "last", "months",
                "month", "india", "india's", "developments", "latest", "significant", "a", "to"}
        words = [w.strip(".,;:'\"()") for w in (req.objective or "").split()]
        key = [w for w in words if w and w.lower() not in stop][:6]
        qs = ([f"{' '.join(key)} {geo}"] if key else []) + [f"{base} {geo}"]
        qs += [f"{c} {geo}" for c in (req.companies or [])[:5]]
        prefs = set(req.source_preferences or [])
        if "government" in prefs or "regulatory" in prefs or not prefs:
            qs.append(f"{base} policy scheme {geo}")
        if "tenders" in prefs:
            qs.append(f"{base} tender {geo}")
        return list(dict.fromkeys(qs))[:8]

    def _ddgs_news(self, q: str, days: int) -> list[Candidate]:
        timelimit = "w" if days <= 7 else "m" if days <= 31 else "y"
        key = f"ddgs:{q}:{timelimit}"
        rows = self._cache_get(key)
        if rows is None:
            try:
                rows = list(self._ddgs_factory().news(q, region="in-en", max_results=15, timelimit=timelimit))
                self._cache_put(key, rows)
            except Exception as exc:  # unofficial endpoint: never fail the run
                self.notes.append(f"DuckDuckGo news unavailable for one query ({type(exc).__name__}).")
                return []
        out = []
        for r in rows or []:
            if not isinstance(r, dict) or not str(r.get("url", "")).startswith("http"):
                continue
            out.append(Candidate(
                url=r["url"], title=r.get("title") or None, publisher=r.get("source") or None,
                published_at=_parse_dt(r.get("date")), snippet=(r.get("body") or None), via="duckduckgo",
            ))
        return out

    def _ddgs_text(self, q: str, days: int) -> list[Candidate]:
        timelimit = "m" if days <= 31 else "y"
        key = f"ddgs-text:{q}:{timelimit}"
        rows = self._cache_get(key)
        if rows is None:
            try:
                rows = list(self._ddgs_factory().text(q, region="in-en", max_results=10, timelimit=timelimit))
                self._cache_put(key, rows)
            except Exception as exc:
                self.notes.append(f"Web search for official/tender pages unavailable ({type(exc).__name__}).")
                return []
        out = []
        for r in rows or []:
            if isinstance(r, dict) and str(r.get("href", "")).startswith("http"):
                out.append(Candidate(url=r["href"], title=r.get("title") or None,
                                     snippet=r.get("body") or None, via="duckduckgo_web"))
        return out

    def _google_news(self, q: str, days: int) -> list[Candidate]:
        import feedparser

        url = f"https://news.google.com/rss/search?q={quote_plus(q)}+when:{days}d&hl=en-IN&gl=IN&ceid=IN:en"
        try:
            status, body = self._get_text(url)
        except httpx.HTTPError:
            self.notes.append("Google News RSS unreachable for one query.")
            return []
        if status >= 400:
            return []
        feed = feedparser.parse(body)
        out = []
        for e in feed.entries[:20]:
            src = e.get("source") or {}
            title = e.get("title") or None
            pub = src.get("title") if isinstance(src, dict) else None
            if title and pub and title.endswith(f" - {pub}"):
                title = title[: -len(pub) - 3]
            out.append(Candidate(
                url=e.get("link", ""), title=title, publisher=pub,
                published_at=_parse_dt(e.get("published")), via="google_news", aggregator=True,
            ))
        return [c for c in out if c.url.startswith("http")]

    def _pib(self, keywords: list[str]) -> list[Candidate]:
        import feedparser

        try:
            status, body = self._get_text("https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3")
        except httpx.HTTPError:
            self.notes.append("PIB press-release feed unreachable.")
            return []
        if status >= 400:
            return []
        feed = feedparser.parse(body)
        kws = [k.lower() for k in keywords if k]
        out = []
        for e in feed.entries:
            t = (e.get("title") or "").strip()
            if not _english(t) or not any(k in t.lower() for k in kws):
                continue
            out.append(Candidate(url=e.get("link", ""), title=t, publisher="Press Information Bureau",
                                 published_at=_parse_dt(e.get("published")), via="pib"))
        return [c for c in out if c.url.startswith("http")]

    def _gdelt(self, q: str, days: int) -> list[Candidate]:
        span = "1m" if days <= 31 else "3m"
        url = ("https://api.gdeltproject.org/api/v2/doc/doc?query="
               + quote_plus(f"{q} sourcecountry:IN sourcelang:english")
               + f"&mode=ArtList&format=json&maxrecords=50&timespan={span}&sort=DateDesc")
        try:
            status, body = self._get_text(url, throttle=self.cfg.gdelt_throttle_seconds)
        except httpx.HTTPError:
            self.notes.append("GDELT unreachable.")
            return []
        try:
            data = json.loads(body)
        except ValueError:
            self.notes.append("GDELT returned a non-JSON response (usually its rate limit); skipped.")
            return []
        if days > 91:
            self.notes.append("GDELT covers roughly the last 3 months only; older coverage comes from other sources.")
        out = []
        for a in (data.get("articles") or []) if isinstance(data, dict) else []:
            if not str(a.get("url", "")).startswith("http"):
                continue
            out.append(Candidate(url=a["url"], title=a.get("title") or None, publisher=a.get("domain") or None,
                                 published_at=_parse_dt(a.get("seendate")), via="gdelt",
                                 date_label="first seen by GDELT"))
        return out

    def discover(self, req: Any, days: int) -> list[Candidate]:
        cands: list[Candidate] = []
        queries = self._queries(req)
        for q in queries:
            cands += self._ddgs_news(q, days)
            cands += self._google_news(q, days)
        keywords = [*(req.companies or []), *(req.industry or "electric vehicle").split()[:3],
                    "electric", "EV", "battery", "charging", "e-mobility"]
        cands += self._pib(keywords)
        prefs = set(req.source_preferences or [])
        base = req.industry or "electric vehicle"
        if "government" in prefs or "regulatory" in prefs:
            cands += self._ddgs_text(f"{base} site:pib.gov.in", days)
        if "tenders" in prefs:
            cands += self._ddgs_text(f"{base} tender site:gem.gov.in OR site:eprocure.gov.in", days)
        cands += self._gdelt(f'"{(req.industry or "electric vehicle")}"', days)
        return cands

    # ------------------------------------------------------- rank & fetch --
    def _rank_key(self, c: Candidate) -> tuple[int, float]:
        from pipeline.research.service import classify_source

        t = classify_source(c.url, self.cfg.company_domains)
        order = {"government": 0, "regulatory": 0, "tender": 0, "company": 1, "news": 2, "web": 3}
        pri = order.get(t, 3) + (2 if c.aggregator else 0)
        ts = c.published_at.timestamp() if c.published_at else 0.0
        return (pri, -ts)

    def select(self, cands: list[Candidate], days: int, relevance: list[str],
               focus: list[str] | None = None) -> list[Candidate]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        rel = [r.lower() for r in relevance if r]
        seen_url: set[str] = set()
        seen_title: set[str] = set()
        out = []
        foc = [f.lower() for f in (focus or []) if f]

        def key(c: Candidate):
            blob = f"{c.title or ''} {c.snippet or ''}".lower()
            hit = 0 if (foc and any(f in blob for f in foc)) else 1
            return (hit, *self._rank_key(c))

        for c in sorted(cands, key=key):
            if c.published_at and c.published_at < cutoff:
                continue
            key = _norm_url(c.url)
            tkey = _norm_text(c.title or "")[:80]
            if key in seen_url or (tkey and tkey in seen_title):
                continue
            blob = f"{c.title or ''} {c.snippet or ''}".lower()
            if rel and not any(r in blob for r in rel):
                continue
            seen_url.add(key)
            if tkey:
                seen_title.add(tkey)
            out.append(c)
            if len(out) >= MAX_SOURCES:
                break
        return out

    def _fetch_one(self, c: Candidate) -> None:
        import trafilatura

        try:
            status, html = self._get_text(c.url)
        except httpx.HTTPError:
            return
        if status >= 400 or not html:
            return
        try:
            text = trafilatura.extract(html, include_comments=False, include_tables=False)
            meta = trafilatura.extract_metadata(html)
        except Exception:
            return
        if text:
            c.text = text[:20000]
            if not c.snippet:
                c.snippet = _lead_sentences(text)
        if meta is not None:
            mt = getattr(meta, "title", None)
            if (not c.title or _generic_title(c.title)) and mt and not _generic_title(mt):
                c.title = mt
        if c.title and _generic_title(c.title) and text:
            # Portal pages (e.g. PIB) carry a site-wide <title>; use the article's first line.
            first = next((ln.strip() for ln in text.splitlines() if 20 <= len(ln.strip()) <= 220), None)
            if first:
                c.title = first
            if not c.published_at and getattr(meta, "date", None):
                c.published_at = _parse_dt(meta.date)

    def fetch(self, cands: list[Candidate]) -> None:
        """Fetch pages in parallel across hosts; requests to one host stay sequential (polite)."""
        if not self.cfg.fetch_pages:
            return
        from concurrent.futures import ThreadPoolExecutor

        by_host: dict[str, list[Candidate]] = {}
        for c in cands:
            if not c.aggregator:
                by_host.setdefault(host_of(c.url), []).append(c)

        def host_worker(items: list[Candidate]) -> None:
            for c in items:
                self._fetch_one(c)

        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(host_worker, by_host.values()))

    # ----------------------------------------------------------- synthesis --
    def _sources(self, run_id: str, cands: list[Candidate]) -> list[dict[str, Any]]:
        from pipeline.research.service import classify_source, domain_of

        now = datetime.now(UTC)
        out = []
        for c in cands:
            out.append({
                "id": _hid(run_id, _norm_url(c.url)),
                "research_run_id": run_id,
                "url": c.url,
                "domain": (domain_of(c.url) if not c.aggregator else (c.publisher or domain_of(c.url))),
                "title": c.title,
                "source_type": self._stype(c),
                "published_at": c.published_at,
                "retrieved_at": now,
                "snippet": (c.snippet or None) and c.snippet[:EXCERPT_CHARS],
                "link_status": "unchecked",
                "discovered_via": c.via + (f" ({c.date_label})" if c.date_label else ""),
            })
        return out

    def _stype(self, c: Candidate) -> str:
        from pipeline.research.service import classify_source

        if c.aggregator:
            return "aggregator"
        t = classify_source(c.url, self.cfg.company_domains)
        # Items found through a news search channel are news articles even when
        # the publisher is not in the static news-domain list.
        if t == "web" and c.via in ("duckduckgo", "google_news", "gdelt"):
            return "news"
        return t

    def _entity(self, text: str, names: list[str]) -> str | None:
        t = (text or "").lower()
        for n in names:
            if n and n.lower().split(" ")[0] in t:
                return n
        return None

    def extractive(self, run_id: str, req: Any, cands: list[Candidate], sources: list[dict[str, Any]]):
        names = list(req.companies or [])
        findings = []
        for c, s in zip(cands, sources, strict=True):
            excerpt = (_lead_sentences(_strip_title(c.text, c.title)) if c.text else None) or c.snippet
            title = c.title or excerpt
            if not title:
                continue
            blob = f"{c.title or ''} {excerpt or ''}"
            findings.append({
                "id": _hid(run_id, "x", s["id"]),
                "research_run_id": run_id,
                "title": title[:300],
                "category": categorize(blob),
                "entity": self._entity(blob, names),
                "industry": req.industry,
                "summary": excerpt,
                "significance": 4 if s["source_type"] in ("government", "regulatory", "tender") else 3,
                "confidence": None,
                "kind": "source_excerpt",
                "event_date": c.published_at.date().isoformat() if c.published_at else None,
                "source_ids": [s["id"]],
                "flags": ["aggregator_link"] if c.aggregator else [],
                "evidence_quote": excerpt if (excerpt and c.text and quote_in_text(excerpt, c.text)) else None,
                "created_at": datetime.now(UTC),
            })
        return cluster_findings(findings)

    def _report_from(self, findings: list[dict[str, Any]], sources: list[dict[str, Any]], mode: str,
                     summary: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        from pipeline.research.service import REPORT_SECTIONS

        report: dict[str, Any] = {k: [] for k in REPORT_SECTIONS}
        report["industry_overview"] = None
        src_by_id = {s["id"]: s for s in sources}
        for f in findings:
            sec = _SECTION_FOR_CATEGORY.get(f["category"], "company_developments")
            s = src_by_id.get((f.get("source_ids") or [None])[0])
            tail = []
            if s and s.get("domain"):
                tail.append(s["domain"])
            if f.get("event_date"):
                tail.append(f["event_date"])
            report[sec].append(f["title"] + (f" ({', '.join(tail)})" if tail else ""))
        types: dict[str, int] = {}
        for s in sources:
            types[s["source_type"]] = types.get(s["source_type"], 0) + 1
        mix = ", ".join(f"{n} {t}" for t, n in sorted(types.items(), key=lambda x: -x[1]))
        cats = sorted({f["category"] for f in findings})
        report["executive_summary"] = summary or (
            f"{len(findings)} developments from {len(sources)} sources ({mix}) across "
            f"{', '.join(c.replace('_', ' ') for c in cats) or 'no categories'}. "
            "Extractive mode: every item below is quoted from its source; no generated prose."
        )
        report["method"] = mode
        report["coverage_notes"] = list(dict.fromkeys(self.notes))
        if extra:
            for k, v in extra.items():
                if k in REPORT_SECTIONS and v:
                    report[k] = v
        return report

    def llm_synthesis(self, run_id: str, req: Any, cands: list[Candidate], sources: list[dict[str, Any]]):
        """Returns (report, findings) or None to signal fallback to extractive."""
        from pipeline.research.service import _category, _clamp_float, _clamp_int, _str_list

        usable = [(i, c, s) for i, (c, s) in enumerate(zip(cands, sources, strict=True)) if (c.text or c.snippet)][:10]
        if not usable:
            return None
        blocks = []
        for n, (_, c, _s) in enumerate(usable, 1):
            body = _strip_title(c.text or c.snippet or "", c.title)[:700]
            blocks.append(f"[{n}] {c.title or ''} ({c.publisher or ''}, {c.published_at.date() if c.published_at else 'date n/a'})\n{body}")
        system = (
            "You are a market-intelligence analyst. Use ONLY the numbered sources. Return JSON with keys: "
            "executive_summary (string), industry_overview (string), market_trends, commercial_opportunities, risks "
            "(arrays of short strings), findings (array of objects with title, category "
            "[expansion|product_launch|partnership|funding|policy|tender|hiring|technology|market_entry|other], "
            "entity, summary, significance 1-5, confidence 0-1, sources (array of source numbers), "
            "evidence_quote (an exact sentence copied verbatim from the first cited source)). "
            "Never invent facts, dates or numbers."
        )
        user = f"Objective: {req.objective[:600]}\n\nSources:\n\n" + "\n\n".join(blocks)
        data = None
        for _attempt in range(2):
            try:
                raw = self._llm_call(system, user) if self._llm_call else self._ollama(system, user)
                data = json.loads(raw)
                if isinstance(data, dict) and isinstance(data.get("findings"), list):
                    break
                data = None
            except Exception as exc:
                log.warning("LLM synthesis attempt failed: %s", type(exc).__name__)
                data = None
        if data is None:
            self.notes.append("Local LLM returned invalid output twice; fell back to extractive mode.")
            return None

        findings = []
        for i, f in enumerate(data.get("findings") or []):
            if not isinstance(f, dict) or not (f.get("title") or f.get("summary")):
                continue
            nums = [int(x) for x in (f.get("sources") or []) if str(x).isdigit() and 1 <= int(x) <= len(usable)]
            cited = [usable[n - 1] for n in nums]
            quote = str(f.get("evidence_quote") or "").strip()
            supported = bool(cited) and any(quote_in_text(quote, (c.text or c.snippet or "")) for _, c, _s in cited)
            flags = [] if supported else ["quote_not_found"]
            first = cited[0][1] if cited else None
            findings.append({
                "id": _hid(run_id, "l", str(i), str(f.get("title"))),
                "research_run_id": run_id,
                "title": str(f.get("title") or f.get("summary"))[:300],
                "category": _category(f.get("category")),
                "entity": (str(f.get("entity") or "").strip() or None),
                "industry": req.industry,
                "summary": str(f.get("summary") or "").strip() or None,
                "significance": _clamp_int(f.get("significance"), 1, 5, 3),
                "confidence": _clamp_float(f.get("confidence"), 0.5),
                "kind": "source_supported" if supported else "analysis",
                "event_date": first.published_at.date().isoformat() if first and first.published_at else None,
                "source_ids": [s["id"] for _, _c, s in cited],
                "flags": flags,
                "evidence_quote": quote if supported else None,
                "created_at": datetime.now(UTC),
            })
        if not findings:
            self.notes.append("Local LLM produced no usable findings; fell back to extractive mode.")
            return None
        extra = {k: _str_list(data.get(k)) for k in ("market_trends", "commercial_opportunities", "risks")}
        report = self._report_from(findings, sources, "llm", summary=str(data.get("executive_summary") or "").strip() or None, extra=extra)
        ov = data.get("industry_overview")
        report["industry_overview"] = " ".join(_str_list(ov)) or None
        report["method"] = f"llm ({self.cfg.llm_model or 'custom'})"
        return report, findings

    def _ollama(self, system: str, user: str) -> str:
        # Native Ollama chat API: lets us disable "thinking" output and raise the
        # context window (the OpenAI-compatible endpoint keeps the small default,
        # which truncated the JSON for multi-source prompts).
        root = self.cfg.ollama_base_url.rstrip("/").removesuffix("/v1")
        r = httpx.post(
            f"{root}/api/chat",
            json={
                "model": self.cfg.llm_model or "",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "format": "json",
                "stream": False,
                "think": False,
                "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 2500},
            },
            timeout=420,
        )
        r.raise_for_status()
        return (r.json().get("message") or {}).get("content") or ""

    # ----------------------------------------------------------- entrypoint --
    def research(self, run_id: str, req: Any, *, status_cb: StatusCb | None = None):
        from pipeline.research.service import NormalizedResult

        cb = status_cb or (lambda _m: None)
        days = _WINDOW_DAYS.get(req.time_window, 91)
        cb("Discovering sources (DuckDuckGo news, Google News, PIB, GDELT)")
        cands = self.discover(req, days)
        relevance = [*(req.companies or []), *[w for w in (req.industry or "").lower().split() if len(w) > 3],
                     "electric", " ev", "ev ", "e-mobility", "battery", "charging"]
        # Named entities from the objective (capitalized words) are ranked first.
        focus = [w.strip(".,;:'\"()") for w in (req.objective or "").split()
                 if w[:1].isupper() and w.lower().strip(".,") not in ("research", "india", "india's", "identify")]
        focus = [" ".join(focus)] if len(focus) > 1 else focus  # "Ola Electric", not "Electric"
        picked = self.select(cands, days, relevance, focus=focus + list(req.companies or []))
        if not picked:
            raise ProviderError(
                "No relevant articles were found in the free sources for this window. "
                "Try a broader objective or a longer time window.",
                code="no_sources",
            )
        cb(f"Fetching {len(picked)} sources")
        self.fetch(picked)
        sources = self._sources(run_id, picked)
        result = None
        if self.synthesis_mode == "llm":
            cb(f"Synthesizing with local LLM ({self.cfg.llm_model or 'custom'})")
            result = self.llm_synthesis(run_id, req, picked, sources)
        if result is None:
            cb("Synthesizing (extractive mode)")
            findings = self.extractive(run_id, req, picked, sources)
            report = self._report_from(findings, sources, "extractive")
        else:
            report, findings = result
            # Sources the LLM did not cite still become labelled verbatim excerpts,
            # so nothing gathered is silently dropped.
            cited = {sid for f in findings for sid in f.get("source_ids") or []}
            pairs = [(c, s) for c, s in zip(picked, sources, strict=True) if s["id"] not in cited]
            if pairs:
                extra = self.extractive(run_id, req, [c for c, _ in pairs], [s for _, s in pairs])
                findings = findings + extra
                for f in extra:
                    sec = _SECTION_FOR_CATEGORY.get(f["category"], "company_developments")
                    report.setdefault(sec, []).append(f["title"])
        return NormalizedResult(report, sources, findings, partial=False, request_id=None)


def _default_ddgs() -> Any:
    from ddgs import DDGS

    return DDGS(timeout=15)


def detect_ollama_model(base_url: str, preferred: str | None = None) -> str | None:
    """Return an installed Ollama chat model >= 7B (preferred families first), or None."""
    root = base_url.rstrip("/").removesuffix("/v1")
    try:
        r = httpx.get(f"{root}/api/tags", timeout=3)
        names = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        return None
    if preferred and preferred in names:
        return preferred

    def big_enough(name: str) -> bool:
        m = re.search(r":(\d+(?:\.\d+)?)b", name.lower())
        # Untagged/latest family defaults (llama3.1, mistral, gemma2, qwen2.5) are >= 7B.
        return float(m.group(1)) >= 7 if m else True

    for fam in ("qwen2.5", "qwen3", "llama3.1", "mistral", "gemma2"):
        for n in names:
            if n.startswith(fam) and "embed" not in n and big_enough(n):
                return n
    return None


def window_start(time_window: str) -> date:
    return (datetime.now(UTC) - timedelta(days=_WINDOW_DAYS.get(time_window, 91))).date()


def host_of(url: str) -> str:
    return (urlparse(url).netloc or "").lower()
