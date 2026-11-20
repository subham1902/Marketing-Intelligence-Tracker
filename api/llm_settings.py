"""AI summary (LLM) connection settings.

Stored server-side in ``data/llm_settings.json`` (gitignored). The API key is
never returned to the browser - only a masked hint. With mode ``off`` (the
default) research runs in extractive mode: every finding is verbatim source
text with its citation, no generated prose.

Modes:
* ``off``               - extractive only (default; works everywhere, no key)
* ``ollama``            - local model via Ollama (``base_url`` default http://localhost:11434)
* ``openai_compatible`` - any OpenAI-compatible chat API: OpenAI, Groq, Gemini
                          (OpenAI endpoint), OpenRouter, Emergent, ...
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from pipeline.config import Settings

_LOCK = threading.Lock()

PRESETS: dict[str, dict[str, str]] = {
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.0-flash"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "model": "meta-llama/llama-3.3-70b-instruct"},
}


def _path(s: Settings) -> Path:
    return s.data_dir / "llm_settings.json"


def load(s: Settings) -> dict[str, Any]:
    p = _path(s)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (ValueError, OSError):
            pass
    # No saved settings: an operator key from the environment (hosted servers) comes first.
    import os

    op_key = os.environ.get("OPERATOR_LLM_API_KEY", "").strip()
    if op_key:
        return {
            "mode": "openai_compatible", "provider": "operator",
            "base_url": os.environ.get("OPERATOR_LLM_BASE_URL", "https://api.groq.com/openai/v1").strip(),
            "model": os.environ.get("OPERATOR_LLM_MODEL", "llama-3.3-70b-versatile").strip(),
            "api_key": op_key, "source": "env",
        }
    # Then the synthesis env switch, defaulting to extractive.
    env = (s.research_synthesis or "").lower()
    if env in ("ollama", "auto"):
        return {"mode": "ollama", "base_url": "", "model": s.research_ollama_model or "", "source": "env"}
    return {"mode": "off", "source": "default"}


def save(s: Settings, data: dict[str, Any]) -> dict[str, Any]:
    current = load(s)
    merged = {
        "mode": data.get("mode", "off"),
        "provider": data.get("provider") or "",
        "base_url": (data.get("base_url") or "").strip(),
        "model": (data.get("model") or "").strip(),
        # Keep the stored key when the client sends none (the UI never sees it).
        "api_key": "" if data.get("clear_key") else ((data.get("api_key") or "").strip() or current.get("api_key", "")),
        "source": "saved",
    }
    with _LOCK:
        s.data_dir.mkdir(parents=True, exist_ok=True)
        _path(s).write_text(json.dumps(merged), encoding="utf-8")
    return merged


def public_view(data: dict[str, Any]) -> dict[str, Any]:
    key = data.get("api_key") or ""
    return {
        "mode": data.get("mode", "off"),
        "provider": data.get("provider") or "",
        "base_url": data.get("base_url") or "",
        "model": data.get("model") or "",
        "has_key": bool(key),
        "key_hint": f"…{key[-4:]}" if len(key) >= 8 else ("set" if key else ""),
        "source": data.get("source", "default"),
    }


def ollama_root(base_url: str) -> str:
    return (base_url or "http://localhost:11434").rstrip("/").removesuffix("/v1")


def openai_call(base_url: str, api_key: str, model: str) -> Callable[[str, str], str]:
    """Return ``call(system, user) -> str`` for an OpenAI-compatible chat API (JSON mode)."""

    def call(system: str, user: str) -> str:
        r = httpx.post(
            base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            },
            timeout=180,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"LLM API error {r.status_code}")
        return r.json()["choices"][0]["message"]["content"] or ""

    return call


def synthesis_label(data: dict[str, Any], ollama_model: str | None) -> str:
    mode = data.get("mode", "off")
    if mode == "openai_compatible" and data.get("api_key") and data.get("model"):
        return f"AI summaries ({data.get('provider') or 'API'}: {data['model']})"
    if mode == "ollama" and ollama_model:
        return f"AI summaries (local {ollama_model})"
    return "extractive (no LLM)"


def test_connection(data: dict[str, Any]) -> tuple[bool, str]:
    """One tiny request to confirm the connection works. Never echoes the key."""
    mode = data.get("mode", "off")
    try:
        if mode == "off":
            return True, "AI summaries are off. Research uses extractive mode with cited sources."
        if mode == "ollama":
            root = ollama_root(data.get("base_url", ""))
            names = [m.get("name", "") for m in httpx.get(f"{root}/api/tags", timeout=5).json().get("models", [])]
            chat = [n for n in names if "embed" not in n]
            if not chat:
                return False, f"Ollama is running at {root} but has no chat models. Run: ollama pull qwen2.5:7b-instruct"
            want = data.get("model") or ""
            if want and want not in names:
                return False, f"Model '{want}' is not installed in Ollama. Installed: {', '.join(chat[:5])}"
            return True, f"Connected to Ollama. Models: {', '.join(chat[:5])}"
        if mode == "openai_compatible":
            if not data.get("api_key"):
                return False, "Add an API key."
            if not data.get("base_url") or not data.get("model"):
                return False, "Add the API base URL and model name."
            out = openai_call(data["base_url"], data["api_key"], data["model"])(
                "Reply with JSON only.", 'Return {"ok": true}'
            )
            json.loads(out)
            return True, f"Connected. {data['model']} returned valid JSON."
    except httpx.ConnectError:
        return False, "Could not reach the server. Check the URL (for Ollama, is it running?)."
    except RuntimeError as exc:
        return False, f"{exc}. Check the key, model name and base URL."
    except (ValueError, KeyError):
        return False, "The model replied, but not with valid JSON. Try another model."
    except Exception as exc:  # pragma: no cover
        return False, f"Connection failed ({type(exc).__name__})."
    return False, "Unknown mode."
