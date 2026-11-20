"""On-demand market research endpoints.

``POST /research`` records a run and processes it in a background task; the
frontend polls ``GET /research/{id}`` for real backend status. No intermediate
"agent steps" are fabricated - status is only queued/running/completed/partial/failed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pipeline.config import Settings
from pipeline.logging_setup import get_logger
from pipeline.research.provider import ContextDevProvider, ProviderError, ResearchProvider
from pipeline.research.service import FINDING_CATEGORIES, ResearchRequest, run_research

from api import guard, llm_settings
from api import research_store as store
from api.db import ApiDB
from api.deps import get_db
from api.schemas import (
    CategoryCount,
    FeedFinding,
    LLMSettingsIn,
    LLMSettingsView,
    LLMTestResult,
    Page,
    ResearchConfig,
    ResearchCreate,
    ResearchFinding,
    ResearchRun,
    ResearchRunSummary,
    ResearchSource,
)

router = APIRouter(tags=["research"])
log = get_logger("api.research")

_WINDOW_DAYS = {"1m": 30, "3m": 91, "6m": 182, "12m": 365}


def _fresh_settings() -> Settings:
    # Not the lru_cached settings: lets a key added to .env take effect without restart.
    return Settings()


def _provider_name(requested: str | None = None) -> str:
    name = (requested or _fresh_settings().research_provider or "open").strip().lower()
    return "contextdev" if name in ("contextdev", "context.dev", "context_dev") else "open"


def _ollama_model(s: Settings) -> str | None:
    """Ollama model to use, or None (only when AI summaries are set to local Ollama)."""
    from pipeline.research.open_provider import detect_ollama_model

    data = llm_settings.load(s)
    if data.get("mode") != "ollama":
        return None
    base = data.get("base_url") or s.ollama_base_url
    return detect_ollama_model(base, data.get("model") or s.research_ollama_model)


def provider_factory(name: str | None = None) -> ResearchProvider:
    """Build the configured provider. Overridden in tests."""
    s = _fresh_settings()
    if _provider_name(name) == "open":
        from pipeline.research.open_provider import OpenConfig, OpenResearchProvider

        data = llm_settings.load(s)
        if data.get("mode") == "openai_compatible" and data.get("api_key") and data.get("model"):
            return OpenResearchProvider(
                OpenConfig(cache_dir=s.data_dir / "research_cache", llm_model=data["model"]),
                llm_call=llm_settings.openai_call(data["base_url"], data["api_key"], data["model"]),
            )
        return OpenResearchProvider(
            OpenConfig(
                cache_dir=s.data_dir / "research_cache",
                llm_model=_ollama_model(s),
                ollama_base_url=llm_settings.ollama_root(data.get("base_url") or s.ollama_base_url),
            )
        )
    return ContextDevProvider(
        s.context_dev_api_key or "",
        base_url=s.context_dev_base_url,
        mode=s.context_dev_mode,
        timeout_seconds=s.research_timeout_seconds,
    )


def _company_domains(db: ApiDB) -> set[str]:
    rows = db.query("SELECT domain FROM raw.competitors WHERE domain IS NOT NULL")
    return {str(r["domain"]).lower().removeprefix("www.") for r in rows if r.get("domain")}


def process_run(db: ApiDB, run_id: str, req: ResearchRequest, provider_name: str | None = None) -> None:
    """Background worker. Never raises: every failure becomes a failed run."""
    provider = None
    try:
        store.set_status(db, run_id, "running")
        provider = provider_factory(provider_name) if provider_name else provider_factory()
        domains = _company_domains(db)
        cfg = getattr(provider, "cfg", None)
        if cfg is not None:
            cfg.company_domains = domains
        result = run_research(
            run_id, req, provider, company_domains=domains,
            status_cb=lambda m: store.set_message(db, run_id, m),
        )
        store.complete_run(
            db,
            run_id,
            report=result.report,
            sources=result.sources,
            findings=result.findings,
            partial=result.partial,
            request_id=result.request_id,
        )
        log.info(
            "research %s done: %d sources, %d findings, partial=%s",
            run_id, len(result.sources), len(result.findings), result.partial,
        )
    except ProviderError as exc:
        log.warning("research %s failed: %s", run_id, exc.code)
        store.fail_run(db, run_id, exc.code, str(exc))
    except Exception as exc:
        log.exception("research %s crashed", run_id)
        store.fail_run(db, run_id, "internal_error", f"Unexpected error: {type(exc).__name__}")
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()


@router.get("/research/config", response_model=ResearchConfig)
def research_config() -> ResearchConfig:
    s = _fresh_settings()
    providers = ["open"] + (["contextdev"] if s.context_dev_api_key else [])
    if _provider_name() == "open":
        return ResearchConfig(
            provider="open",
            live_available=True,
            mode="free",
            synthesis=llm_settings.synthesis_label(llm_settings.load(s), _ollama_model(s)),
            providers=providers,
        )
    return ResearchConfig(
        provider="context.dev",
        live_available=bool(s.context_dev_api_key),
        mode=s.context_dev_mode,
        synthesis="context.dev answers",
        providers=providers,
    )


@router.post("/research", response_model=ResearchRun, status_code=202, dependencies=[Depends(guard.run_limit)])
def create_research(
    body: ResearchCreate,
    background: BackgroundTasks,
    request: Request,
    db: ApiDB = Depends(get_db),
) -> dict:
    run_id = f"rr-{datetime.now(UTC):%Y%m%d}-{uuid.uuid4().hex[:8]}"
    today = date.today()
    pname = _provider_name(body.provider)
    has_key = pname == "open" or bool(_fresh_settings().context_dev_api_key)
    run = {
        "id": run_id,
        "objective": body.objective.strip(),
        "industry": body.industry,
        "geography": body.geography,
        "time_window": body.time_window,
        "date_from": today - timedelta(days=_WINDOW_DAYS[body.time_window]),
        "date_to": today,
        "companies": body.companies,
        "source_preferences": list(body.source_preferences),
        "status": "queued" if has_key else "failed",
        "provider": "open" if pname == "open" else "context.dev",
    }
    store.create_run(db, run)
    if not has_key:
        store.fail_run(
            db,
            run_id,
            "missing_key",
            "Live research is not configured: set CONTEXT_DEV_API_KEY in the server .env. "
            "The demo snapshot remains available.",
        )
    else:
        req = ResearchRequest(
            objective=run["objective"],
            industry=body.industry,
            geography=body.geography,
            time_window=body.time_window,
            companies=body.companies,
            source_preferences=list(body.source_preferences),
        )
        background.add_task(process_run, request.app.state.db, run_id, req, pname)
    found = store.get_run(db, run_id)
    assert found is not None
    return found


@router.get("/research", response_model=list[ResearchRunSummary])
def list_research(db: ApiDB = Depends(get_db), limit: int = Query(default=50, ge=1, le=200)) -> list[dict]:
    return store.list_runs(db, limit)


@router.get("/research/{run_id}", response_model=ResearchRun)
def get_research(run_id: str, db: ApiDB = Depends(get_db)) -> dict:
    found = store.get_run(db, run_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Research run '{run_id}' not found.")
    return found


@router.get("/research/{run_id}/sources", response_model=list[ResearchSource])
def get_research_sources(run_id: str, db: ApiDB = Depends(get_db)) -> list[dict]:
    if not store.get_run(db, run_id):
        raise HTTPException(status_code=404, detail=f"Research run '{run_id}' not found.")
    return store.list_sources(db, run_id)


@router.get("/research/{run_id}/findings", response_model=list[ResearchFinding])
def get_research_findings(run_id: str, db: ApiDB = Depends(get_db)) -> list[dict]:
    if not store.get_run(db, run_id):
        raise HTTPException(status_code=404, detail=f"Research run '{run_id}' not found.")
    return store.list_findings(db, run_id)


@router.get("/findings", response_model=Page[FeedFinding])
def findings_feed(
    db: ApiDB = Depends(get_db),
    category: str | None = Query(default=None),
    kind: str | None = Query(
        default=None, pattern="^(verified_fact|analysis|source_supported|source_excerpt)$"
    ),
    include_demo: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page:
    if category and category not in FINDING_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Unknown category '{category}'.")
    items, total = store.feed(
        db, category=category, kind=kind, include_demo=include_demo, limit=limit, offset=offset
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/findings/categories", response_model=list[CategoryCount])
def findings_categories(db: ApiDB = Depends(get_db)) -> list[dict]:
    return store.category_counts(db)


# ------------------------- company refresh (free) -------------------------- #
@router.post(
    "/companies/{competitor_id}/refresh", response_model=ResearchRun, status_code=202,
    dependencies=[Depends(guard.run_limit)],
)
def refresh_company(
    competitor_id: str, background: BackgroundTasks, request: Request, db: ApiDB = Depends(get_db)
) -> dict:
    """Run the free open provider for one company over the last month."""
    from api import repository as repo

    comp = repo.get_competitor(db, competitor_id)
    if not comp:
        raise HTTPException(status_code=404, detail=f"Company '{competitor_id}' not found.")
    body = ResearchCreate(
        objective=f"Latest developments for {comp['name']} in India",
        industry=comp.get("industry"),
        time_window="1m",
        companies=[comp["name"]],
        source_preferences=["official_company", "news"],
        provider="open",
    )
    return create_research(body, background, request, db)


@router.get("/companies/{competitor_id}/developments", response_model=list[FeedFinding])
def company_developments(competitor_id: str, db: ApiDB = Depends(get_db)) -> list[dict]:
    from api import repository as repo

    comp = repo.get_competitor(db, competitor_id)
    if not comp:
        raise HTTPException(status_code=404, detail=f"Company '{competitor_id}' not found.")
    return store.company_developments(db, comp["name"])


# ------------------------------ AI summaries -------------------------------- #
@router.get("/settings/llm", response_model=LLMSettingsView)
def get_llm_settings() -> dict:
    s = _fresh_settings()
    view = llm_settings.public_view(llm_settings.load(s))
    view["active"] = llm_settings.synthesis_label(llm_settings.load(s), _ollama_model(s))
    view["presets"] = llm_settings.PRESETS
    return view


@router.put("/settings/llm", response_model=LLMSettingsView, dependencies=[Depends(guard.require_admin)])
def put_llm_settings(body: LLMSettingsIn) -> dict:
    s = _fresh_settings()
    saved = llm_settings.save(s, body.model_dump())
    view = llm_settings.public_view(saved)
    view["active"] = llm_settings.synthesis_label(saved, _ollama_model(s))
    view["presets"] = llm_settings.PRESETS
    return view


@router.post("/settings/llm/test", response_model=LLMTestResult, dependencies=[Depends(guard.require_admin)])
def test_llm_settings(body: LLMSettingsIn) -> LLMTestResult:
    s = _fresh_settings()
    data = {**llm_settings.load(s), **{k: v for k, v in body.model_dump().items() if v not in (None, "")}}
    if body.clear_key:
        data["api_key"] = ""
    ok, msg = llm_settings.test_connection(data)
    return LLMTestResult(ok=ok, message=msg)
