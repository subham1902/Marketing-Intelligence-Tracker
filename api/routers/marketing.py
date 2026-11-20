"""Marketing Analysis endpoints (background job, polled by the UI)."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pipeline.logging_setup import get_logger
from pipeline.marketing import service
from pydantic import BaseModel, Field

from api import marketing_store as store
from api.db import ApiDB
from api.deps import get_db

router = APIRouter(tags=["marketing"])
MAX_CONCURRENT = 3


def _clean(name: str) -> str:
    """Collapse whitespace and drop control / markup characters from a free-text company name."""
    no_tags = re.sub(r"<[^>]*>", " ", name)
    no_markup = re.sub(r"[\x00-\x1f<>{}\[\]\\]", " ", no_tags)
    return re.sub(r"\s+", " ", no_markup).strip()[:80]


log = get_logger("api.marketing")


class MarketingCreate(BaseModel):
    company: str | None = Field(None, description="Tracked company id")
    name: str | None = Field(None, max_length=120, description="Any company name (temporary entity)")


def _tracked(db: ApiDB) -> list[dict[str, Any]]:
    try:
        return db.query("SELECT id, name, industry FROM raw.competitors ORDER BY name")
    except Exception:
        return []


def provider_factory():
    """Overridden in tests. Reuses the research provider (and its configured LLM)."""
    from api.routers.research import provider_factory as pf

    return pf("open")


def _llm_of(provider: Any):
    if getattr(provider, "synthesis_mode", "") != "llm":
        return None
    return getattr(provider, "_llm_call", None) or getattr(provider, "_ollama", None)


def process(db: ApiDB, aid: str, company: dict[str, Any], rivals: dict[str, Any]) -> None:
    provider = None
    try:
        store.set_stage(db, aid, "Gathering evidence")
        provider = provider_factory()
        result, mode, items = service.run(provider, company, rivals, llm=_llm_of(provider),
                                          status_cb=lambda s: store.set_stage(db, aid, s))
        if not items:
            store.fail(db, aid, "No public sources were reachable from this server. "
                                "Open the latest captured analysis instead.")
            return
        store.complete(db, aid, mode, result, items)
    except Exception as exc:
        log.exception("marketing %s crashed", aid)
        store.fail(db, aid, f"Unexpected error: {type(exc).__name__}. Open the latest captured analysis.")
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()


@router.post("/marketing/analyses", status_code=202)
def create_analysis(body: MarketingCreate, background: BackgroundTasks, request: Request,
                    db: ApiDB = Depends(get_db)) -> dict:
    tracked = _tracked(db)
    by_id = {c["id"]: c for c in tracked}
    if body.company and body.company in by_id:
        c = by_id[body.company]
        company = service.build_company(c["id"], c["name"], c.get("industry"))
    elif body.name and _clean(body.name):
        name = _clean(body.name)
        company = service.build_company(service.slug(name), name, None)
    else:
        raise HTTPException(status_code=422, detail="Choose a tracked company or type a company name.")
    active = db.query(
        "SELECT id, company FROM research.marketing_analyses WHERE status IN ('queued','running')"
    )
    same = next((x for x in active if x["company"] == company["id"]), None)
    if same:  # a run for this company is already in progress: reuse it instead of duplicating work
        return store.get(db, same["id"]) or {}
    if len(active) >= MAX_CONCURRENT:
        raise HTTPException(status_code=429, detail="Several analyses are already running. "
                                                    "Try again in a minute or open a captured analysis.")
    aid = f"mk-{datetime.now(UTC):%Y%m%d}-{uuid.uuid4().hex[:8]}"
    store.create(db, aid, company["id"], company["name"])
    background.add_task(process, request.app.state.db, aid, company, service.build_rivals(tracked))
    return store.get(db, aid) or {}


@router.get("/marketing/analyses")
def list_analyses(company: str | None = Query(None), db: ApiDB = Depends(get_db)) -> list[dict]:
    return store.list_(db, company)


@router.get("/marketing/analyses/{aid}")
def get_analysis(aid: str, db: ApiDB = Depends(get_db)) -> dict:
    a = store.get(db, aid)
    if not a:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return a
