"""Research provider adapter.

The product talks to a small ``ResearchProvider`` protocol so it is not
permanently coupled to one web-data vendor. ``ContextDevProvider`` implements
it over raw HTTPX against the documented Context.dev endpoints:

* ``POST /web/answers``  - agentic research returning ``json_content`` + ``sources`` (URL strings)
* ``POST /web/search``   - ranked results with ``url``/``title``/``description``/``relevance``

The API key is read server-side and is never logged or echoed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from pipeline.logging_setup import get_logger

log = get_logger(__name__)


class ProviderError(Exception):
    """A provider call failed in a way we can explain to the user."""

    def __init__(self, message: str, *, code: str = "provider_error", status: int | None = None):
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass
class AnswerResult:
    json_content: dict[str, Any]
    sources: list[str]
    partial: bool = False
    request_id: str | None = None
    credits_consumed: int | None = None


@dataclass
class SearchHit:
    url: str
    title: str | None = None
    snippet: str | None = None
    relevance: str | None = None


@dataclass
class SearchResult:
    hits: list[SearchHit] = field(default_factory=list)
    partial: bool = False


class ResearchProvider(Protocol):
    name: str

    def answer(self, task: str, json_format: dict[str, Any]) -> AnswerResult: ...

    def search(
        self,
        query: str,
        *,
        num_results: int = 10,
        include_domains: list[str] | None = None,
        country: str | None = None,
        freshness: str | None = None,
    ) -> SearchResult: ...


_STATUS_MESSAGES = {
    400: ("bad_request", "The research provider rejected the request as invalid."),
    401: ("unauthorized", "The research provider rejected the API key (401). Check CONTEXT_DEV_API_KEY."),
    402: ("credits_exhausted", "The research provider account is out of credits (402)."),
    403: ("forbidden", "The research provider key lacks permission for this request (403)."),
    408: ("timeout", "The research provider timed out before finishing (408)."),
    429: ("rate_limited", "The research provider rate limit was hit (429). Wait a minute and retry."),
    500: ("provider_failed", "The research provider could not gather usable evidence (500)."),
    504: ("timeout", "The research provider exceeded its time limit (504)."),
}


class ContextDevProvider:
    name = "context.dev"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.context.dev/v1",
        mode: str = "fast",
        timeout_seconds: int = 180,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ProviderError("CONTEXT_DEV_API_KEY is not configured.", code="missing_key")
        self._mode = mode if mode in ("fast", "ultra") else "fast"
        self._timeout_ms = max(1000, min(timeout_seconds * 1000, 300_000))
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            # Client timeout slightly above the provider-side deadline.
            timeout=httpx.Timeout(self._timeout_ms / 1000 + 30, connect=15),
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            res = self._client.post(path, json=body)
        except httpx.TimeoutException as exc:
            raise ProviderError("The research provider did not respond in time.", code="timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Could not reach the research provider ({type(exc).__name__}).", code="network"
            ) from exc

        if res.status_code >= 400:
            code, msg = _STATUS_MESSAGES.get(
                res.status_code, ("provider_error", f"Research provider error ({res.status_code}).")
            )
            detail = ""
            try:
                detail = str(res.json().get("message") or "")[:300]
            except ValueError:
                pass
            log.warning("provider %s -> %s %s", path, res.status_code, code)
            raise ProviderError(f"{msg} {detail}".strip(), code=code, status=res.status_code)

        try:
            data = res.json()
        except ValueError as exc:
            raise ProviderError("The research provider returned invalid JSON.", code="invalid_json") from exc
        if not isinstance(data, dict):
            raise ProviderError("The research provider returned an unexpected payload.", code="invalid_json")
        return data

    def answer(self, task: str, json_format: dict[str, Any]) -> AnswerResult:
        body = {
            "task": task[:2000],
            "mode": self._mode,
            "json_format": json_format,
            "timeoutOpts": {"milliseconds": self._timeout_ms, "behavior": "return-partial"},
            "tags": ["market-intelligence-tracker"],
        }
        data = self._post("/web/answers", body)
        content = data.get("json_content")
        if isinstance(content, str):
            # Defensive: some deployments may return the answer as a JSON string.
            import json

            try:
                content = json.loads(content)
            except ValueError:
                content = {"executive_summary": content}
        if not isinstance(content, dict):
            content = {}
        sources = [s for s in (data.get("sources") or []) if isinstance(s, str) and s.startswith("http")]
        meta = data.get("key_metadata") or {}
        return AnswerResult(
            json_content=content,
            sources=sources,
            partial=bool(data.get("partial")),
            request_id=data.get("request_id"),
            credits_consumed=meta.get("credits_consumed") if isinstance(meta, dict) else None,
        )

    def search(
        self,
        query: str,
        *,
        num_results: int = 10,
        include_domains: list[str] | None = None,
        country: str | None = None,
        freshness: str | None = None,
    ) -> SearchResult:
        body: dict[str, Any] = {"query": query[:500], "numResults": max(1, min(num_results, 100))}
        if include_domains:
            body["includeDomains"] = include_domains[:100]
        if country:
            body["country"] = country
        if freshness:
            body["freshness"] = freshness
        data = self._post("/web/search", body)
        hits = []
        for r in data.get("results") or []:
            if not isinstance(r, dict) or not isinstance(r.get("url"), str):
                continue
            hits.append(
                SearchHit(
                    url=r["url"],
                    title=r.get("title") or None,
                    snippet=r.get("description") or None,
                    relevance=r.get("relevance"),
                )
            )
        return SearchResult(hits=hits, partial=bool(data.get("partial")))
