"""Deterministic signal extraction (no LLM).

Every function works on *evidence items*: dicts with ``id``, ``url``, ``domain``,
``title``, ``date`` (ISO or None), ``text`` (fetched page text or snippet) and
``fetched`` (True when ``text`` came from the page itself, not a headline).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

# --------------------------------------------------------------- sentences --
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'₹(])")


def sentences(text: str, max_len: int = 400) -> list[str]:
    out = []
    for raw in _SENT_SPLIT.split(re.sub(r"\s+", " ", text or "")):
        s = raw.strip()
        if 30 <= len(s) <= max_len:
            out.append(s)
    return out


def mentions(sentence: str, names: list[str]) -> bool:
    low = sentence.lower()
    return any(n.lower() in low for n in names if n)


# ----------------------------------------------------------------- figures --
FIGURE_RE = re.compile(
    r"(?:₹|rs\.?|inr|usd|us\$|\$)\s?\d[\d,]*(?:\.\d+)?\s?(?:crore|cr|lakh|billion|million|bn|mn)?"
    r"|\d[\d,]*(?:\.\d+)?\s?(?:crore|cr|lakh|billion|million)\b"
    r"|\d+(?:\.\d+)?\s?(?:%|per cent|percent)"
    r"|\d[\d,]{2,}\s?(?:units|vehicles)",
    re.IGNORECASE,
)
FIGURE_KEYWORDS = {
    "revenue": "Revenue", "ebitda": "EBITDA", "net profit": "Profit", "profit": "Profit",
    "loss": "Loss", "margin": "Margin", "market share": "Market share", "units": "Volume",
    "sales": "Volume", "volume": "Volume", "valuation": "Valuation", "funding": "Funding",
}
_YEAR_RE = re.compile(r"\b(?:FY\s?'?(\d{2,4})|Q[1-4]\s?FY\s?'?(\d{2,4})|(20[12]\d))\b", re.IGNORECASE)


def extract_figures(items: list[dict[str, Any]], names: list[str]) -> list[dict[str, Any]]:
    """Financial/operating figures. Only from fetched page text (never a bare headline)."""
    out, seen = [], set()
    for it in items:
        if not it.get("fetched"):
            continue
        for s in sentences(it.get("text", "")):
            if not mentions(s, names):
                continue
            low = s.lower()
            metric = next((v for k, v in FIGURE_KEYWORDS.items() if k in low), None)
            if not metric:
                continue
            vals = [m.group(0).strip() for m in FIGURE_RE.finditer(s)]
            if not vals:
                continue
            key = (metric, vals[0].lower())
            if key in seen:
                continue
            seen.add(key)
            ym = _YEAR_RE.search(s)
            period = ym.group(0).upper().replace(" ", "") if ym else None
            out.append({"metric": metric, "value": vals[0], "values": vals, "period": period,
                        "quote": s, "evidence_id": it["id"]})
    return out[:20]


# ------------------------------------------------------------- competitors --
def competitor_mentions(items: list[dict[str, Any]], company: list[str],
                        rivals: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Count sentences where the company and a known rival are co-mentioned."""
    counts: Counter[str] = Counter()
    quotes: dict[str, list[tuple[str, str]]] = {}
    for it in items:
        for s in sentences(it.get("text", "")) or [it.get("title") or ""]:
            if not mentions(s, company):
                continue
            for rid, aliases in rivals.items():
                if mentions(s, aliases):
                    counts[rid] += 1
                    quotes.setdefault(rid, []).append((s, it["id"]))
    return [{"id": rid, "co_mentions": n,
             "quotes": [{"quote": q, "evidence_id": e} for q, e in quotes[rid][:3]]}
            for rid, n in counts.most_common()]


# -------------------------------------------------------------------- tone --
POSITIVE = {"growth", "grew", "record", "strong", "surge", "profit", "gain", "launch", "expands",
            "expansion", "leader", "leading", "best", "award", "rise", "rises", "up", "boost",
            "milestone", "success", "innovative", "partnership", "wins", "positive", "beat"}
NEGATIVE = {"loss", "losses", "decline", "fall", "falls", "drop", "recall", "complaint", "complaints",
            "fire", "delay", "delays", "weak", "slump", "probe", "penalty", "lawsuit", "layoff",
            "layoffs", "down", "cut", "concern", "issue", "issues", "negative", "miss", "slowdown"}
_WORD = re.compile(r"[a-z]+")


def tone_score(text: str) -> float:
    """(pos - neg) / (pos + neg), in [-1, 1]; 0 when no lexicon word appears."""
    words = _WORD.findall((text or "").lower())
    p = sum(w in POSITIVE for w in words)
    n = sum(w in NEGATIVE for w in words)
    return 0.0 if p + n == 0 else round((p - n) / (p + n), 3)


def tone(items: list[dict[str, Any]], names: list[str]) -> dict[str, Any]:
    scored = []
    for it in items:
        rel = [s for s in sentences(it.get("text", "")) if mentions(s, names)] or [it.get("title") or ""]
        sc = tone_score(" ".join(rel))
        best = max(rel, key=tone_score) if rel else ""
        worst = min(rel, key=tone_score) if rel else ""
        scored.append({"evidence_id": it["id"], "date": it.get("date"), "score": sc,
                       "best": best, "worst": worst})
    if not scored:
        return {"score": None, "n": 0, "trend": [], "most_positive": None, "most_negative": None}
    avg = round(sum(s["score"] for s in scored) / len(scored), 3)
    by_year: dict[str, list[float]] = {}
    for s in scored:
        if s["date"]:
            by_year.setdefault(str(s["date"])[:4], []).append(s["score"])
    trend = [{"period": y, "score": round(sum(v) / len(v), 3), "n": len(v)} for y, v in sorted(by_year.items())]
    hi = max(scored, key=lambda s: s["score"])
    lo = min(scored, key=lambda s: s["score"])
    return {
        "score": avg, "n": len(scored), "trend": trend,
        "label": f"Indicative tone from {len(scored)} articles",
        "most_positive": {"quote": hi["best"], "evidence_id": hi["evidence_id"]} if hi["score"] > 0 else None,
        "most_negative": {"quote": lo["worst"], "evidence_id": lo["evidence_id"]} if lo["score"] < 0 else None,
    }


# ------------------------------------------------------------------- plans --
PLAN_RE = re.compile(
    r"\b(plans? to|planning to|will launch|will (?:set up|invest|expand|introduce|enter|begin)|aims? to|"
    r"targets?|targeting|by 20(?:2[6-9]|3\d)|is set to|intends to|expects to)\b",
    re.IGNORECASE,
)


def plans(items: list[dict[str, Any]], names: list[str]) -> list[dict[str, Any]]:
    out, seen = [], set()
    for it in items:
        for s in sentences(it.get("text", "")):
            if mentions(s, names) and PLAN_RE.search(s) and s not in seen:
                seen.add(s)
                out.append({"quote": s, "evidence_id": it["id"], "date": it.get("date")})
    return out[:10]


# --------------------------------------------------------------- 7P cues --
MIX_KEYWORDS: dict[str, list[str]] = {
    "Product": ["launch", "model", "variant", "range", "battery", "feature", "scooter", "car", "platform",
                "technology", "product"],
    "Price": ["price", "priced", "pricing", "discount", "₹", "affordable", "cost", "subsidy", "emi", "offer"],
    "Place": ["dealership", "dealer", "showroom", "store", "outlet", "distribution", "network", "cities",
              "export", "retail", "touchpoint"],
    "Promotion": ["campaign", "advertis", "brand ambassador", "marketing", "promotion", "sponsor",
                  "social media", "festive"],
    "People": ["employee", "hiring", "ceo", "leadership", "staff", "workforce", "talent", "layoff"],
    "Process": ["service", "after-sales", "delivery", "waiting", "booking", "app", "software update",
                "complaint", "turnaround"],
    "Physical evidence": ["experience centre", "experience center", "showroom", "design", "charging",
                          "grid", "facility", "plant"],
}


def mix_cues(items: list[dict[str, Any]], names: list[str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {p: [] for p in MIX_KEYWORDS}
    for it in items:
        for s in sentences(it.get("text", "")):
            if not mentions(s, names):
                continue
            low = s.lower()
            for p, kws in MIX_KEYWORDS.items():
                if any(k in low for k in kws) and len(out[p]) < 6:
                    out[p].append({"quote": s, "evidence_id": it["id"], "tone": tone_score(s)})
    return out


def keyword_hits(items: list[dict[str, Any]], names: list[str], kws: list[str],
                 limit: int = 4) -> list[dict[str, Any]]:
    """Sentences mentioning the company and any keyword (the evidence for a rule)."""
    out = []
    for it in items:
        for s in sentences(it.get("text", "")):
            low = s.lower()
            if mentions(s, names) and any(k in low for k in kws):
                out.append({"quote": s, "evidence_id": it["id"]})
                if len(out) >= limit:
                    return out
    return out


NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    return {m.group(0).replace(",", "") for m in NUM_RE.finditer(text or "")}


def invented_numbers(claim: str, evidence_texts: list[str]) -> set[str]:
    """Numbers in ``claim`` that appear in none of the cited evidence texts."""
    have: set[str] = set()
    for t in evidence_texts:
        have |= numbers_in(t)
    return {n for n in numbers_in(claim) if n not in have}
