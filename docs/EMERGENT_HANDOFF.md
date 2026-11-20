# Emergent hand-off: Market Intelligence Tracker

This app runs fully on a hosted server with **no paid keys and no local LLM**. Research uses free public sources (DuckDuckGo news, Google News RSS, PIB, GDELT) and an extractive synthesis mode, which writes no generated prose.

## 1. Architecture in brief

```
web/  Next.js 14 (App Router, Tailwind, shadcn-style UI, Tremor charts)
  └─ calls /api/*  ──►  FastAPI (api/)  ──►  DuckDB file (data/compete.duckdb)
                                 │
                                 ├─ Path A: company intelligence (tracked companies, signals, pricing, hiring)
                                 │          raw.* tables + dbt marts (main_marts.*)
                                 └─ Path B: market research (pipeline/research/)
                                            ResearchProvider abstraction:
                                              open_provider.py   free, keyless (default)
                                              provider.py        Context.dev (optional, paid)
                                            research.* tables (runs, sources, findings)
```

- **Provider abstraction:** both providers implement `ResearchProvider`. The open provider also exposes `research()`, which `service.run_research` uses.
- **Provenance:** every finding carries a `kind`:
  - `source_excerpt`: verbatim source text (extractive mode).
  - `source_supported`: an LLM finding whose evidence quote was found verbatim in the cited source.
  - `verified_fact`: Context.dev "Provider-cited fact".
  - `analysis`: anything that couldn't be verified.

  Unknown dates and titles stay `null` and display as "Not available".
- **Persistence:** DuckDB file under `data/`.
  - First boot on an empty server auto-seeds the labelled `[Sample]` EV demo data, builds the dbt marts, and loads the **real** captured research runs from `config/research_snapshot.json`.
  - Disable this with `COMPETE_AUTOSEED=0`.

## 2. Running it on Emergent

Backend (either form works):

```bash
# Emergent template layout: backend/server.py re-exports the real app
cd backend && pip install -r requirements.txt && uvicorn server:app --host 0.0.0.0 --port 8001
# or from the repo root
pip install -r requirements.txt && uvicorn api.main:app --host 0.0.0.0 --port 8001
```

- Every API route is served under both `/` and **`/api`**. Emergent's ingress forwards `/api/*` to the backend unchanged, so no code changes are needed.
- Health check: `GET /api/health` returns `{"status":"ok"}`.
- First boot takes about 1–2 minutes (seed + dbt). Later boots are instant.

Frontend:

```bash
cd web && npm install && npm run dev -- -p 3000      # or: npm run build && npm start -- -p 3000
```

- The browser calls same-origin `/api/*`. On Emergent the ingress routes that to the backend.
- If requests reach Next instead of the ingress, the Next rewrite proxies `/api/*` to `API_PROXY_TARGET`, or to `http://127.0.0.1:$BACKEND_PORT` (default 8000). On Emergent, set `BACKEND_PORT=8001`.
- The frontend lives in `web/`, not `frontend/`. Point Emergent's frontend service at `web/` (or ask the Emergent agent to move it and update paths).
- `NEXT_PUBLIC_STATIC_DATA=0` (the default) means live backend mode.

Environment (`.env` at the repo root; see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `COMPETE_RESEARCH_PROVIDER` | `open` | `open` (free) or `contextdev` (paid) |
| `COMPETE_RESEARCH_SYNTHESIS` | `auto` | `auto` uses Ollama if a ≥7B model is reachable, otherwise extractive. Use `extractive` on servers. |
| `CONTEXT_DEV_API_KEY` | empty | Optional paid provider. Server-side only. |
| `COMPETE_CORS_ORIGINS` | `http://localhost:3000` | Add the hosted frontend origin if you call the API cross-origin |
| `COMPETE_AUTOSEED` | `1` | First-boot seed + marts + real snapshot |
| `COMPETE_LLM_PROVIDER` | `mock` | Legacy page-change extractor (Path A). `mock` needs no key. |

**DuckDB on hosted containers:** the file lives in `data/`. If the container filesystem is ephemeral, every redeploy re-seeds, and the real snapshot comes back from `config/research_snapshot.json`. New research done on the hosted app persists only while the container lives, unless `data/` is on persistent storage.

## 3. Files Emergent must not break

| File | Why |
|---|---|
| `pipeline/research/open_provider.py` | Free provider: discovery, fetch, quote verification, extractive synthesis |
| `pipeline/research/provider.py` | Context.dev adapter and `ResearchProvider` protocol |
| `pipeline/research/service.py` | Provenance rules, source classification, window flags |
| `api/research_store.py` | `research.*` schema; columns are added with `ALTER ... IF NOT EXISTS` at startup |
| `api/routers/research.py` | `/research`, `/findings`, `/companies/{id}/refresh`, `/companies/{id}/developments` |
| `api/main.py` | `/api` mirror and first-boot autoseed |
| `api/schemas.py` | API contract; `web/src/lib/research-types.ts` mirrors it |
| `config/research_snapshot.json` | Real captured runs for hosted first boot |
| `warehouse/dbt/` | Marts behind the dashboard, company and pricing charts |

## 4. Suggested prompt for Emergent

> This repo is a working Market Intelligence Tracker (Next.js 14 frontend in `web/`, FastAPI backend in `api/`, DuckDB + dbt). First **audit** it: run the backend on port 8001 and the frontend on 3000, then click through Dashboard → Companies → company page → Refresh news → Research → run research → report tabs → Feed. Then **enhance the UI only**: visual design, layout, responsiveness, charts, empty and loading states. **Do not replace the backend, the database, the data model, or the provenance labels** ("Source excerpt", "Source-supported (quote verified)", "Provider-cited fact", "Analysis", "Demo snapshot", "[Sample]"). Keep every API call going through `web/src/lib/api.ts` and `web/src/lib/research-api.ts`. Do not invent data in the UI.

## 5. Enhancement ideas

**P0 (demo impact)**
- A redesigned research report: a hero summary, a category chip bar, and source cards in a side panel with hover-to-highlight between findings and sources.
- A dashboard "Market pulse": a findings-per-category chart and the latest government and policy items.
- Company page: a live developments timeline that merges real findings with the change history.
- Optional LLM summaries with the Emergent universal LLM key, behind the same quote-verification rule (`quote_in_text`): only verified quotes are labelled "source-supported".

**P1**
- Scheduled company refresh: a daily cron calling `POST /api/companies/{id}/refresh`.
- PDF or shareable export of a research report.
- Saved research templates per industry (the product is industry-agnostic; EV is only the demo).
- Deduplicating findings across runs and building an entity/company graph.
