"""Run one Marketing Analysis end to end."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from pipeline.marketing import synth
from pipeline.marketing.gather import gather

ALIASES = {
    "tata-motors": ["Tata Motors", "Tata.ev", "Tata EV", "Nexon EV"],
    "mahindra": ["Mahindra", "M&M", "XUV400", "BE 6"],
    "tvs-motor": ["TVS Motor", "TVS iQube", "TVS"],
    "ather-energy": ["Ather Energy", "Ather", "Rizta"],
    "ola-electric": ["Ola Electric", "Ola S1", "Ola"],
    "exide": ["Exide Industries", "Exide"],
    "amara-raja": ["Amara Raja", "Amaron"],
    "bajaj-auto": ["Bajaj Auto", "Chetak"],
    "hero-motocorp": ["Hero MotoCorp", "Vida"],
    "mg-motor": ["JSW MG", "MG Motor", "MG Windsor"],
    "hyundai": ["Hyundai Motor India", "Hyundai"],
    "maruti-suzuki": ["Maruti Suzuki", "Maruti"],
}
EXTRA_RIVALS = {
    "bajaj-auto": ("Bajaj Auto", "EV & Mobility - Two/Three-wheelers"),
    "hero-motocorp": ("Hero MotoCorp", "EV & Mobility - Two-wheelers"),
    "mg-motor": ("JSW MG Motor", "EV & Mobility - Passenger"),
    "hyundai": ("Hyundai", "EV & Mobility - Passenger"),
    "maruti-suzuki": ("Maruti Suzuki", "EV & Mobility - Passenger"),
}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "company"


def build_company(cid: str, name: str, industry: str | None = None) -> dict[str, Any]:
    return {"id": cid, "name": name, "industry": industry, "aliases": ALIASES.get(cid, [name])}


def build_rivals(tracked: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {c["id"]: build_company(c["id"], c["name"], c.get("industry")) for c in tracked}
    for rid, (n, ind) in EXTRA_RIVALS.items():
        out.setdefault(rid, build_company(rid, n, ind))
    return out


def analyse(company: dict[str, Any], items: list[dict[str, Any]], rivals: dict[str, dict[str, Any]],
            llm: Callable[[str, str], str] | None = None) -> tuple[dict[str, Any], str]:
    result = synth.rule_based(company, items, rivals)
    if llm is not None and items:
        return synth.ai_enrich(result, company, items, llm)
    return result, "rule"


def run(provider: Any, company: dict[str, Any], rivals: dict[str, dict[str, Any]],
        llm: Callable[[str, str], str] | None = None,
        status_cb: Callable[[str], None] | None = None, max_pages: int = 30):
    items = gather(provider, company["name"], max_pages=max_pages, status_cb=status_cb)
    if status_cb:
        status_cb("Analysing")
    result, mode = analyse(company, items, rivals, llm)
    return result, mode, items
