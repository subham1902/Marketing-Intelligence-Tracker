"""In-app guide: deterministic retrieval over config/app_guide.yaml + live status.

Pure functions (no FastAPI) so they are easy to test. The deterministic path is
the default and needs no LLM or key. An optional local-LLM rephrase is done by
the router only when explicitly enabled and reachable.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from pipeline.config import REPO_ROOT

GUIDE_PATH = REPO_ROOT / "config" / "app_guide.yaml"
META_MARK = "\n\n<<META>>"

_STOP = {
    "the", "a", "an", "is", "are", "do", "does", "i", "my", "me", "to", "of", "in", "on", "for",
    "and", "or", "it", "this", "that", "what", "how", "can", "why", "when", "be", "with",
    "you", "your", "there", "here", "at", "by", "from", "get", "show", "about", "please", "tell",
}

PAGE_NAMES = {
    "/dashboard": "Overview", "/research/view": "a research report", "/research": "Research",
    "/feed": "Feed", "/competitors/": "a company profile", "/competitors": "Companies",
    "/signals": "Signals", "/changes": "Changes", "/reports": "Reports", "/settings": "Settings",
}

STARTERS = {
    "/research/view": ["What does Source excerpt mean?", "How do I open a source?", "Why is my run slow?"],
    "/research": ["How do I run research?", "What do the templates do?", "Does it work without AI?"],
    "/feed": ["How do I hide the demo snapshot?", "What does Analysis mean?", "How do I filter by category?"],
    "/competitors/": ["How do I refresh this company's news?", "What are [Sample] signals?", "What's the status of my research?"],
    "/competitors": ["How do I add a company?", "How do I refresh company news?", "What's in the feed today?"],
    "/dashboard": ["Where do I run research?", "What's the status of my research?", "What does this app do?"],
}
DEFAULT_STARTERS = ["Where do I run research?", "What does Source excerpt mean?", "What just happened?"]


@dataclass
class Entry:
    id: str
    title: str
    keywords: list[str]
    answer: str
    route: str | None = None
    action_label: str | None = None
    related: list[str] = field(default_factory=list)


@dataclass
class GuideReply:
    text: str
    actions: list[dict[str, str]] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    confident: bool = True
    kind: str = "kb"  # kb | status | activity | low_confidence


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9+\[\]]+", (text or "").lower().replace("ctrl k", "ctrl+k"))
    out = []
    for t in toks:
        if t in _STOP or len(t) < 2:
            continue
        out.append(t[:-1] if len(t) > 4 and t.endswith("s") else t)
    return out


@lru_cache(maxsize=1)
def load_entries(path: str = str(GUIDE_PATH)) -> tuple[Entry, ...]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return tuple(
        Entry(
            id=e["id"], title=e["title"], keywords=[str(k) for k in e.get("keywords", [])],
            answer=str(e["answer"]).strip(), route=e.get("route"), action_label=e.get("action_label"),
            related=list(e.get("related", [])),
        )
        for e in data.get("entries", [])
    )


class BM25:
    """Small BM25 index. Title and keywords are weighted above the answer body."""

    def __init__(self, entries: tuple[Entry, ...], k1: float = 1.4, b: float = 0.75) -> None:
        self.entries = entries
        self.k1, self.b = k1, b
        self.docs = [
            tokenize(e.title) * 3 + tokenize(" ".join(e.keywords)) * 3 + tokenize(e.answer) for e in entries
        ]
        self.avgdl = sum(len(d) for d in self.docs) / max(1, len(self.docs))
        self.tf = [Counter(d) for d in self.docs]
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        # Whole keyword phrases ("source excerpt", "refresh news") get a direct bonus.
        self.phrases = [[k.lower() for k in e.keywords if " " in k] for e in entries]

    def scores(self, query: str) -> list[float]:
        q = tokenize(query)
        ql = (query or "").lower()
        out = []
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i])
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf.get(t, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            s += sum(2.5 for p in self.phrases[i] if p in ql)
            out.append(s)
        return out


@lru_cache(maxsize=1)
def _index() -> BM25:
    return BM25(load_entries())


def page_name(pathname: str | None) -> str:
    p = pathname or ""
    for prefix, name in PAGE_NAMES.items():
        if p.startswith(prefix):
            return name
    return "the app"


def starters(pathname: str | None) -> list[str]:
    p = pathname or ""
    for prefix, items in STARTERS.items():
        if p.startswith(prefix):
            return items
    return DEFAULT_STARTERS


def retrieve(query: str, pathname: str | None = None, k: int = 3) -> list[tuple[Entry, float]]:
    idx = _index()
    sc = idx.scores(query)
    p = pathname or ""
    where = bool(re.match(r"\s*(where|which page|how do i (find|get to))", (query or "").lower()))
    ranked = []
    for e, s in zip(idx.entries, sc, strict=True):
        if where and e.id.startswith("nav-"):
            s *= 1.6  # "where is X" wants a place, not a procedure
        if s > 0 and e.route and p and (p == e.route or p.startswith(e.route + "/")):
            s *= 1.25  # mild boost for help about the page you're on
        ranked.append((e, s))
    ranked.sort(key=lambda x: -x[1])
    return ranked[:k]


# ----------------------------------------------------------------- intents --
_STATUS = re.compile(r"\b(status|running|progress|latest run|my research|last run|recent run|is it done|finished)\b", re.I)
_FEED = re.compile(r"\b(feed today|in the feed|what'?s new|findings today|today)\b", re.I)
_COUNT = re.compile(r"\bhow many (companies|competitors)\b|\bcompan(y|ies) count\b", re.I)
_ACTIVITY = re.compile(r"\b(what just happened|what happened|why did (that|it) fail|last action|what did i (just )?do)\b", re.I)


def intent(message: str) -> str | None:
    if _ACTIVITY.search(message):
        return "activity"
    if _COUNT.search(message):
        return "count"
    if _STATUS.search(message):
        return "status"
    if _FEED.search(message):
        return "feed"
    return None


def status_reply(runs: list[dict[str, Any]]) -> GuideReply:
    if not runs:
        return GuideReply("You haven't run any research yet. Open **Research** to start one.",
                          [{"label": "Open Research", "route": "/research"}], kind="status")
    lines = []
    actions = []
    for r in runs[:3]:
        st = r.get("status")
        stage = r.get("status_message") if st in ("queued", "running") else None
        label = {"completed": "completed", "partial": "partial", "failed": "failed",
                 "running": "running", "queued": "queued"}.get(st, st)
        obj = (r.get("objective") or "")[:70]
        extra = (f" · {stage}" if stage else
                 f" · {r.get('finding_count', 0)} findings, {r.get('source_count', 0)} sources" if st in ("completed", "partial") else
                 f" · {r.get('error_message')}" if st == "failed" and r.get("error_message") else "")
        demo = " (demo)" if r.get("is_demo") else ""
        lines.append(f"- **{label}**{demo}: {obj}{extra}")
        actions.append({"label": "Open run" if len(actions) else "Open latest run",
                        "route": f"/research/view?id={r['id']}"})
    running = sum(1 for r in runs if r.get("status") in ("queued", "running"))
    head = (f"{running} run{'s are' if running != 1 else ' is'} in progress. " if running else "Nothing is running right now. ")
    return GuideReply(head + "Your latest runs:\n\n" + "\n".join(lines), actions[:2], kind="status")


def feed_reply(categories: list[dict[str, Any]], total: int) -> GuideReply:
    if not total:
        return GuideReply("The feed is empty so far. Run research to add findings.",
                          [{"label": "Open Research", "route": "/research"}], kind="status")
    top = ", ".join(f"{c['category'].replace('_', ' ')} ({c['count']})" for c in categories[:5])
    return GuideReply(f"The feed has **{total} findings** across all runs. Top categories: {top}.",
                      [{"label": "Open Feed", "route": "/feed"}], kind="status")


def count_reply(n: int) -> GuideReply:
    return GuideReply(f"You're tracking **{n} companies**. Open **Companies** to see them, or add more in **Settings**.",
                      [{"label": "Open Companies", "route": "/competitors"}], kind="status")


def activity_reply(activity: list[dict[str, Any]]) -> GuideReply:
    if not activity:
        return GuideReply("I don't see any recent activity in this browser yet. Start something (like a research "
                          "run) and ask again, or open the **Activity** drawer in the top bar.", kind="activity")
    recent = activity[-10:][::-1]
    fails = [a for a in recent if a.get("status") == "error"]
    lines = []
    for a in recent[:5]:
        st = {"success": "done", "error": "failed", "pending": "in progress"}.get(a.get("status", ""), a.get("status", ""))
        dur = f" in {a['durationMs'] / 1000:.1f}s" if a.get("durationMs") else ""
        err = f" ({a['error']})" if a.get("error") else ""
        lines.append(f"- {a.get('label', 'Action')}: {st}{dur}{err}")
    head = (f"Your last action that failed: **{fails[0].get('label')}**"
            f"{' (' + fails[0]['error'] + ')' if fails[0].get('error') else ''}. " if fails else "Here's what just happened, newest first:")
    actions = [{"label": "Open " + a.get("label", "page")[:24], "route": a["route"]} for a in recent if a.get("route")][:1]
    return GuideReply(head + "\n\n" + "\n".join(lines), actions, kind="activity")


def kb_reply(query: str, pathname: str | None) -> GuideReply:
    hits = retrieve(query, pathname, k=4)
    best, score = hits[0] if hits else (None, 0.0)
    if not best or score < 2.0:
        topics = [e.title for e, s in hits if s > 0][:3] or [e.title for e in load_entries()[:3]]
        return GuideReply(
            "I'm not sure about that. I can only help with what this app actually does, and I'd rather not guess. "
            "These topics might be close:",
            suggestions=topics[:3], confident=False, kind="low_confidence",
        )
    actions = [{"label": best.action_label, "route": best.route}] if best.route and best.action_label else []
    by_id = {e.id: e for e in load_entries()}
    sugg = [by_id[r].title for r in best.related if r in by_id][:3]
    if len(sugg) < 3:
        sugg += [e.title for e, s in hits[1:] if e.title not in sugg and s > 0][: 3 - len(sugg)]
    return GuideReply(best.answer, actions, sugg[:3], [best.id] + [e.id for e, s in hits[1:3] if s > score * 0.6])


def answer(message: str, pathname: str | None, activity: list[dict[str, Any]] | None,
           runs: list[dict[str, Any]], feed_categories: list[dict[str, Any]], feed_total: int,
           companies: int) -> GuideReply:
    kind = intent(message)
    if kind == "activity":
        r = activity_reply(activity or [])
    elif kind == "count":
        r = count_reply(companies)
    elif kind == "status":
        r = status_reply(runs)
    elif kind == "feed":
        r = feed_reply(feed_categories, feed_total)
    else:
        return kb_reply(message, pathname)
    if not r.suggestions:
        r.suggestions = starters(pathname)[:3]
    return r


def meta_line(r: GuideReply) -> str:
    return META_MARK + json.dumps(
        {"actions": r.actions, "suggestions": r.suggestions, "sources": r.sources, "kind": r.kind},
        ensure_ascii=False,
    )


def word_chunks(text: str) -> list[str]:
    """Split into word-sized chunks that keep whitespace, for natural streaming."""
    return re.findall(r"\S+\s*|\s+", text)


def parse_stream(body: str) -> tuple[str, dict[str, Any]]:
    """Client-side helper mirrored in tests: split streamed text from the META trailer."""
    if META_MARK in body:
        text, meta = body.split(META_MARK, 1)
        return text, json.loads(meta)
    return body, {}
