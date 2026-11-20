"""Framework synthesis: rule-based (default) and optional AI mode with validation.

Rule-based prose only restates evidence. Every rated item carries ``evidence``
(quotes + evidence ids), a ``label`` (Evidence / Analysis / Forecast / Not found)
and a ``how`` string explaining the rule that produced it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from pipeline.marketing import signals as sg

NOT_FOUND = "Not found in public sources"


def _rate(n: int, strong: int = 3, moderate: int = 1) -> str:
    return "strong" if n >= strong else "moderate" if n >= moderate else "unknown"


def _ev(hits: list[dict[str, Any]], k: int = 2) -> list[dict[str, Any]]:
    return [{"quote": h["quote"], "evidence_id": h["evidence_id"]} for h in hits[:k]]


MOAT_KW = {
    "Brand": ["brand", "trusted", "iconic", "loyal", "recogni"],
    "Scale / cost": ["largest", "capacity", "plant", "scale", "volume", "cost advantage", "gigafactory"],
    "Network effects": ["ecosystem", "community", "network of", "users", "platform"],
    "Switching costs": ["subscription", "service plan", "warranty", "ecosystem", "software"],
    "IP / technology": ["patent", "in-house", "r&d", "technology", "proprietary", "cell"],
    "Distribution": ["dealership", "dealer", "showroom", "outlet", "touchpoint", "distribution", "stores"],
    "Regulatory": ["pli", "fame", "pm e-drive", "subsidy", "incentive", "approval", "certification"],
}

STAKEHOLDERS = {
    # name: (keywords, power, interest) - placement is Analysis by default rule
    "Customers": (["customer", "buyer", "rider", "consumer", "booking"], "high", "high"),
    "Investors": (["investor", "shareholder", "ipo", "funding", "stake", "valuation"], "high", "high"),
    "Government / regulators": (["government", "ministry", "subsidy", "policy", "regulator", "pli", "fame"],
                                "high", "medium"),
    "Suppliers / partners": (["supplier", "partner", "partnership", "tie-up", "collaborat", "cell"],
                             "medium", "high"),
    "Employees": (["employee", "staff", "workforce", "hiring", "layoff"], "low", "high"),
    "Dealers": (["dealer", "dealership", "distributor", "franchise"], "medium", "high"),
    "Community": (["community", "csr", "city", "citizens", "environment"], "low", "medium"),
}

SEGMENT_KW = {
    "Geographic": ["tier 2", "tier-2", "tier 3", "cities", "rural", "urban", "states", "export", "metro"],
    "Demographic": ["young", "youth", "women", "families", "income", "students", "millennial"],
    "Behavioural": ["commut", "first-time", "upgrade", "enthusiast", "performance", "daily", "delivery"],
    "B2B": ["fleet", "commercial", "b2b", "logistics", "enterprise", "government order", "oem"],
    "B2C": ["retail", "consumer", "personal", "household"],
}

RECO_RULES = [
    # (trigger_key, action, impact, effort, kpi)
    ("weak_promotion", "Run a targeted digital campaign around the strongest proven product claim",
     "Higher consideration in core segments", "Medium", "Share of search / enquiries per week"),
    ("weak_place", "Expand touchpoints in under-served cities via partner dealers or experience zones",
     "Wider reach, shorter time-to-test-ride", "High", "New touchpoints and test rides per month"),
    ("negative_tone", "Address the recurring complaint themes publicly with a service-quality fix",
     "Recover tone and repeat purchase intent", "Medium", "Share of negative coverage; complaint volume"),
    ("high_rivalry", "Sharpen positioning on one differentiator versus the most co-mentioned rival",
     "Clearer reason to choose, less price war", "Low", "Win-rate versus named rival"),
    ("buyer_power", "Reduce dependence on discounts and subsidies with value bundles (service, warranty)",
     "Margin protection", "Medium", "Average selling price and discount depth"),
    ("weak_price", "Publish transparent pricing and EMI options for the main range",
     "Lower purchase friction", "Low", "Configurator-to-booking conversion"),
    ("profit_unknown", "Track and disclose unit economics publicly to strengthen the investor story",
     "Investor and partner confidence", "Low", "Coverage citing margins"),
    ("plans_exist", "Pre-build demand for the announced plans (waitlists, pilots) ahead of launch",
     "Faster ramp after launch", "Medium", "Waitlist sign-ups"),
    ("weak_moat", "Invest in the weakest moat dimension that rivals already use (see Moat)",
     "Longer-term defensibility", "High", "Moat evidence count next quarter"),
]


def rule_based(company: dict[str, Any], items: list[dict[str, Any]],
               rivals: dict[str, dict[str, Any]]) -> dict[str, Any]:
    names = company["aliases"]
    by_id = {i["id"]: i for i in items}
    rival_alias = {rid: r["aliases"] for rid, r in rivals.items() if rid != company["id"]}

    figs = sg.extract_figures(items, names)
    comp = sg.competitor_mentions(items, names, rival_alias)
    tone = sg.tone(items, names)
    plans = sg.plans(items, names)
    mix = sg.mix_cues(items, names)
    hits = lambda kws, k=4: sg.keyword_hits(items, names, kws, k)  # noqa: E731

    # ---- profitability
    periods = sorted({f["period"] for f in figs if f["period"]})
    profitability = {
        "figures": figs[:10],
        "trend": ("Figures cover " + ", ".join(periods) + " (compare quotes for direction).")
        if len(periods) >= 2 else None,
        "label": "Evidence" if figs else "Not found",
        "summary": f"{len(figs)} financial or operating figures quoted from fetched pages." if figs else NOT_FOUND,
        "how": "Sentences naming the company that contain a money/percent/units figure and a metric keyword "
               "(revenue, EBITDA, profit, loss, margin, market share, units). Headlines are never used.",
    }

    # ---- moat
    moat = []
    for dim, kws in MOAT_KW.items():
        h = hits(kws)
        moat.append({"dimension": dim, "rating": _rate(len(h), 4, 2) if h else "unknown",
                     "evidence": _ev(h), "label": "Analysis" if h else "Not found"})
    for m in moat:
        if m["rating"] == "moderate" and len(m["evidence"]) < 2:
            m["rating"] = "weak"

    # ---- stakeholders
    stake = []
    for name, (kws, power, interest) in STAKEHOLDERS.items():
        h = hits(kws, 2)
        stake.append({"name": name, "power": power, "interest": interest, "evidence": _ev(h),
                      "label": "Analysis", "mentions": len(h)})

    # ---- porter
    n_rivals = len([c for c in comp if c["co_mentions"] >= 1])
    def lvl(n: int, hi: int, mid: int) -> str:
        return "high" if n >= hi else "medium" if n >= mid else "low"
    buyer = hits(["price cut", "discount", "subsidy", "cheaper", "price war", "offer"])
    supplier = hits(["supplier", "import", "cell", "semiconductor", "rare earth", "shortage", "china"])
    entrants = hits(["new entrant", "startup", "enters", "entry", "launches its first", "new player"])
    subs = hits(["petrol", "internal combustion", " ice ", "cng", "hybrid", "public transport", "metro rail"])
    rivalry_ev = [q for c in comp[:3] for q in c["quotes"][:1]]
    porter = [
        {"force": "Rivalry", "level": lvl(n_rivals, 4, 2), "evidence": rivalry_ev,
         "reason": f"{n_rivals} tracked rivals co-mentioned with {company['name']}.",
         "how": "high if ≥4 rivals are co-mentioned, medium if 2 to 3, else low."},
        {"force": "Threat of new entrants", "level": lvl(len(entrants), 3, 1), "evidence": _ev(entrants),
         "reason": f"{len(entrants)} sentences about new entrants.", "how": "high ≥3 entrant mentions, medium ≥1."},
        {"force": "Buyer power", "level": lvl(len(buyer), 3, 1), "evidence": _ev(buyer),
         "reason": f"{len(buyer)} price-cut / discount / subsidy mentions.",
         "how": "high if ≥3 price-cut, discount or subsidy-dependence mentions, medium ≥1."},
        {"force": "Supplier power", "level": lvl(len(supplier), 3, 1), "evidence": _ev(supplier),
         "reason": f"{len(supplier)} supply-side dependency mentions.",
         "how": "high ≥3 mentions of imports, cells, chips or shortages, medium ≥1."},
        {"force": "Threat of substitutes", "level": lvl(len(subs), 3, 1), "evidence": _ev(subs),
         "reason": f"{len(subs)} substitute (petrol, CNG, hybrid, transit) mentions.",
         "how": "high ≥3 substitute mentions, medium ≥1."},
    ]

    # ---- competition
    competition = []
    for c in comp[:5]:
        r = rivals.get(c["id"], {})
        competition.append({"id": c["id"], "name": r.get("name", c["id"]), "co_mentions": c["co_mentions"],
                            "doing": c["quotes"][:2], "segment": r.get("industry"), "label": "Evidence"})

    # ---- need gaps
    gaps = []
    for theme, kws in {
        "Service and after-sales": ["service", "after-sales", "repair", "waiting"],
        "Reliability / quality": ["recall", "fire", "defect", "issue", "complaint"],
        "Charging / infrastructure": ["charging", "charger", "range anxiety", "infrastructure"],
        "Affordability": ["expensive", "price", "subsidy cut", "cost"],
    }.items():
        h = [x for x in hits(kws, 6) if sg.tone_score(x["quote"]) < 0]
        if h:
            gaps.append({"gap": theme, "evidence": _ev(h), "label": "Analysis",
                         "why": f"{len(h)} negative-tone sentences on this theme suggest an unmet need."})

    # ---- segmentation
    segs = []
    for seg, kws in SEGMENT_KW.items():
        h = hits(kws, 2)
        segs.append({"segment": seg, "evidence": _ev(h), "label": "Evidence" if h else "Not found"})

    # ---- positioning past/present/future
    dated = sorted([i for i in items if i.get("date")], key=lambda i: i["date"])
    cut = str(dated[len(dated) // 2]["date"])[:10] if dated else None
    past = [i for i in dated if cut and str(i["date"])[:10] < cut][:3]
    present = [i for i in dated if cut and str(i["date"])[:10] >= cut][-3:]
    def tl(lst):
        return [{"quote": i.get("title") or "", "evidence_id": i["id"], "date": i.get("date")} for i in lst]
    sector = (company.get("industry") or "").lower()
    axes = ("Price", "Technology") if "battery" not in sector else ("Price", "Scale")
    def place(cid: str, aliases: list[str]) -> dict[str, float]:
        tech = len(sg.keyword_hits(items, aliases, ["technology", "in-house", "software", "premium", "cell"], 10))
        price = len(sg.keyword_hits(items, aliases, ["premium", "expensive", "flagship"], 10)) - \
            len(sg.keyword_hits(items, aliases, ["affordable", "budget", "cheaper", "entry-level"], 10))
        return {"x": max(0.0, min(1.0, 0.5 + price * 0.1)), "y": max(0.0, min(1.0, 0.2 + tech * 0.08))}
    points = [{"name": company["name"], "self": True, **place(company["id"], names)}]
    for c in competition[:4]:
        points.append({"name": c["name"], "self": False, **place(c["id"], rivals[c["id"]]["aliases"])})
    positioning = {
        "past": tl(past), "present": tl(present),
        "future": [{**p, "label": "Evidence"} for p in plans[:3]],
        "forecast": (f"Forecast: if stated plans proceed, {company['name']} moves toward the "
                     f"{'higher-technology' if plans else 'current'} end of its segment.") if plans else None,
        "map": {"x_axis": axes[0], "y_axis": axes[1], "points": points, "label": "Analysis",
                "how": "x = premium vs affordable keyword balance; y = technology keyword density, per company."},
    }

    # ---- GTM
    gtm_kw = ["launch", "dealer", "showroom", "price", "partnership", "export", "campaign", "online"]
    gtm_items = [i for i in dated if any(k in (i.get("title") or "").lower() for k in gtm_kw)]
    gtm = {"timeline": tl(gtm_items[-8:]), "future": [{**p, "label": "Evidence"} for p in plans[3:6] or plans[:2]],
           "forecast": "Forecast: channel and launch activity continues along the announced plans."
           if plans else None}

    # ---- 7P
    mix_score = []
    for p, cues in mix.items():
        avg = sum(c["tone"] for c in cues) / len(cues) if cues else 0
        rating = "unknown" if not cues else "strong" if (len(cues) >= 3 and avg > 0) else \
            "weak" if avg < 0 else "average"
        mix_score.append({"p": p, "rating": rating, "evidence": _ev(cues), "cues": len(cues),
                          "label": "Analysis" if cues else "Not found"})

    # ---- recommendations
    triggers: dict[str, str] = {}
    mp = {m["p"]: m["rating"] for m in mix_score}
    if mp.get("Promotion") in ("weak", "unknown"):
        triggers["weak_promotion"] = f"7P Promotion rated {mp.get('Promotion')}"
    if mp.get("Place") in ("weak", "unknown"):
        triggers["weak_place"] = f"7P Place rated {mp.get('Place')}"
    if mp.get("Price") == "weak":
        triggers["weak_price"] = "7P Price rated weak"
    if tone.get("score") is not None and tone["score"] < 0:
        triggers["negative_tone"] = f"Indicative tone {tone['score']:+.2f}"
    if porter[0]["level"] == "high":
        triggers["high_rivalry"] = porter[0]["reason"]
    if porter[2]["level"] in ("high", "medium"):
        triggers["buyer_power"] = porter[2]["reason"]
    if not figs:
        triggers["profit_unknown"] = "Profitability: not found in public sources"
    if plans:
        triggers["plans_exist"] = f"{len(plans)} stated plans found"
    weak = [m["dimension"] for m in moat if m["rating"] in ("weak", "unknown")]
    if weak:
        triggers["weak_moat"] = "Moat weak/unknown: " + ", ".join(weak[:3])
    recos = []
    for _i, (key, action, impact, effort, kpi) in enumerate(RECO_RULES):
        if key in triggers:
            recos.append({"priority": len(recos) + 1, "action": action, "why": triggers[key], "trigger": key,
                          "impact": impact, "effort": effort, "kpi": kpi, "label": "Rule-based recommendation"})
    recos = recos[:8]

    # ---- snapshot + coverage
    coverage = {
        "Profitability": min(1.0, len(figs) / 4), "Moat": sum(bool(m["evidence"]) for m in moat) / len(moat),
        "Stakeholders": sum(bool(s["evidence"]) for s in stake) / len(stake),
        "Five forces": sum(bool(p["evidence"]) for p in porter) / 5,
        "Competition": min(1.0, len(competition) / 3), "Tone": min(1.0, tone["n"] / 10),
        "Segmentation": sum(bool(s["evidence"]) for s in segs) / len(segs),
        "Plans": min(1.0, len(plans) / 3), "7P": sum(bool(m["evidence"]) for m in mix_score) / 7,
    }
    fetched = sum(1 for i in items if i.get("fetched"))
    snapshot = {
        "summary": (f"{company['name']} ({company.get('industry') or 'sector n/a'}): "
                    f"{len(items)} public sources ({fetched} read in full), {len(competition)} rivals co-mentioned, "
                    f"{len(plans)} stated plans, indicative tone "
                    f"{'n/a' if tone['score'] is None else f'{tone['score']:+.2f}'}."),
        "sector": company.get("industry"), "evidence_count": len(items), "fetched_count": fetched,
        "coverage": {k: round(v, 2) for k, v in coverage.items()},
    }
    _ = by_id
    return {
        "snapshot": snapshot, "profitability": profitability, "moat": moat, "stakeholders": stake,
        "porter": porter, "competition": competition, "tone": tone, "need_gaps": gaps,
        "segmentation": segs, "positioning": positioning, "gtm": gtm, "mix": mix_score,
        "recommendations": recos,
    }


# ------------------------------------------------------------------ AI mode --
def validate_ai_claims(claims: list[dict[str, Any]], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reject claims with invented numbers; downgrade claims whose quote isn't in the cited source."""
    by_id = {i["id"]: i for i in items}
    out = []
    for c in claims:
        ids = [e for e in (c.get("evidence_ids") or []) if e in by_id]
        texts = [(by_id[e].get("text") or "") + " " + (by_id[e].get("title") or "") for e in ids]
        if not ids or sg.invented_numbers(str(c.get("claim", "")), texts):
            continue
        quote = str(c.get("quote") or "")
        verified = bool(quote) and any(quote.lower() in t.lower() for t in texts)
        out.append({"claim": str(c["claim"]), "evidence_ids": ids, "quote": quote if verified else None,
                    "label": "AI analysis" if verified else "AI analysis (not quote-verified)"})
    return out


def ai_enrich(result: dict[str, Any], company: dict[str, Any], items: list[dict[str, Any]],
              llm: Callable[[str, str], str]) -> tuple[dict[str, Any], str]:
    """Add AI insights + recommendations on top of the rule-based result. Falls back on failure."""
    packets = "\n".join(f"[{i['id']}] {(i.get('title') or '')[:120]} :: {(i.get('text') or '')[:500]}"
                        for i in items[:18])
    system = ("You are a marketing strategist. Use ONLY the numbered evidence. Every claim must cite "
              "evidence ids and include a short exact quote from that evidence. Never add numbers that "
              "are not in the evidence. Reply with JSON only.")
    user = (f"Company: {company['name']}\nEvidence:\n{packets}\n\nReturn "
            '{"insights":[{"claim":"","evidence_ids":[""],"quote":""}],'
            '"recommendations":[{"action":"","why":"","evidence_ids":[""],"quote":"","impact":"","effort":"",'
            '"kpi":""}]} with 4-6 insights and 3-5 recommendations.')
    for _attempt in range(2):
        try:
            raw = llm(system, user)
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(m.group(0) if m else raw)
            insights = validate_ai_claims(data.get("insights") or [], items)
            recs_in = [{**r, "claim": f"{r.get('action', '')} {r.get('why', '')}"}
                       for r in data.get("recommendations") or []]
            recs = []
            for r in recs_in:
                vs = validate_ai_claims([r], items)
                v = vs[0] if vs else None
                if v:
                    recs.append({"action": r.get("action", ""), "why": r.get("why", ""), "impact": r.get("impact"),
                                 "effort": r.get("effort"), "kpi": r.get("kpi"), "evidence_ids": v["evidence_ids"],
                                 "label": "AI recommendation", "verified": v["quote"] is not None})
            if not insights:
                raise ValueError("no valid insights")
            out = dict(result)
            out["ai_insights"] = insights
            n = len(result["recommendations"])
            out["recommendations"] = ([{**r, "priority": i + 1} for i, r in enumerate(recs)] +
                                      [{**r, "priority": len(recs) + r["priority"]}
                                       for r in result["recommendations"]])[: max(8, n)]
            return out, "ai"
        except Exception:
            continue
    return result, "rule"
