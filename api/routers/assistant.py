"""In-app guide endpoint: POST /assistant/chat (streams text/plain + META trailer)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pipeline.assistant import guide
from pipeline.config import Settings
from pipeline.logging_setup import get_logger
from pydantic import BaseModel, Field

from api import llm_settings
from api import research_store as store
from api.db import ApiDB
from api.deps import get_db

router = APIRouter(tags=["assistant"])
log = get_logger("api.assistant")


class ChatTurn(BaseModel):
    role: str = Field(max_length=20)
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    pathname: str | None = Field(default=None, max_length=300)
    history: list[ChatTurn] = Field(default_factory=list, max_length=6)
    activity: list[dict[str, Any]] = Field(default_factory=list, max_length=10)


def _context(db: ApiDB) -> dict[str, Any]:
    return {
        "runs": store.list_runs(db, 5),
        "feed_categories": store.category_counts(db),
        "feed_total": int(db.scalar(
            "SELECT count(*) FROM research.research_findings f JOIN research.research_runs r "
            "ON r.id=f.research_run_id WHERE r.status IN ('completed','partial')")),
        "companies": int(db.scalar("SELECT count(*) FROM raw.competitors")),
    }


def _rephrase(reply: guide.GuideReply, message: str) -> str | None:
    """Optional: rephrase a knowledge-base answer with the connected LLM, staying within it."""
    if reply.kind != "kb":
        return None
    data = llm_settings.load(Settings())
    system = ("You are the in-app guide. Rewrite the GUIDE ANSWER so it directly answers the user's question. "
              "Use ONLY facts in the guide answer; never add features, steps or numbers. Keep markdown bold for UI "
              'names. 2-5 sentences. Return JSON {"answer": "..."}.')
    user = f"Question: {message}\n\nGUIDE ANSWER:\n{reply.text}"
    try:
        if data.get("mode") == "openai_compatible" and data.get("api_key") and data.get("model"):
            out = llm_settings.openai_call(data["base_url"], data["api_key"], data["model"])(system, user)
        elif data.get("mode") == "ollama":
            import httpx

            root = llm_settings.ollama_root(data.get("base_url", ""))
            httpx.get(f"{root}/api/tags", timeout=2).raise_for_status()  # reachable within 2 s
            from pipeline.research.open_provider import detect_ollama_model

            model = data.get("model") or detect_ollama_model(root)
            if not model:
                return None
            r = httpx.post(f"{root}/api/chat", timeout=25, json={
                "model": model, "stream": False, "format": "json", "think": False,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "options": {"temperature": 0.1, "num_predict": 400}})
            out = (r.json().get("message") or {}).get("content") or ""
        else:
            return None
        text = str(json.loads(out).get("answer") or "").strip()
        return text if 20 <= len(text) <= 1500 else None
    except Exception as exc:
        log.info("guide rephrase skipped: %s", type(exc).__name__)
        return None


@router.post("/assistant/chat")
async def assistant_chat(body: ChatIn, db: ApiDB = Depends(get_db)) -> StreamingResponse:
    ctx = await asyncio.to_thread(_context, db)
    reply = guide.answer(body.message, body.pathname, body.activity, **ctx)
    better = await asyncio.to_thread(_rephrase, reply, body.message)
    if better:
        reply.text = better

    async def gen() -> AsyncIterator[bytes]:
        for chunk in guide.word_chunks(reply.text):
            yield chunk.encode("utf-8")
            await asyncio.sleep(0.03)
        yield guide.meta_line(reply).encode("utf-8")

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/assistant/starters")
def assistant_starters(pathname: str | None = None) -> dict[str, Any]:
    return {"page": guide.page_name(pathname), "starters": guide.starters(pathname)}
