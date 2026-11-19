# Market Intelligence Tracker: implementation log

Built on [`yassnemo/compete`](https://github.com/yassnemo/compete) (MIT). The upstream licence and attribution are kept.
Upstream commit: `ebc32b20c2016282976d2375af5821b530fa66bf`. Branch: `hackathon/market-intelligence`.

## Completed

- **Baseline.** `uv sync` and `npm ci` both succeeded, the 41 upstream tests passed, and the seeded demo started on Windows.
  - Issue: on Windows, `scripts/demo.py` crashed with `UnicodeEncodeError` (cp1252 console).
  - Fix: the script now switches stdout to UTF-8.
- **Provider adapter** (`pipeline/research/provider.py`).
  - A `ResearchProvider` protocol, implemented by `ContextDevProvider` over raw HTTPX.
  - Endpoints: `POST /v1/web/answers` in fast mode, and `POST /v1/web/search` for titles and snippets.
  - Errors: 401, 402, 403, 408, 429, 500 and 504, timeouts, network failures and invalid JSON all become a `ProviderError` with a readable message.
  - The API key is never logged.
- **Research service** (`pipeline/research/service.py`).
  - Builds the task text (≤2000 characters) from the objective, geography, time window, industry, companies and source preferences.
  - Answers takes no geo, date or domain fields, so these go into the task text.
  - Normalizes the `json_content` returned by the provider.
  - Integrity rules:
    - Source URLs come only from the provider. Titles and snippets come only from Search, matched by exact URL.
    - Publication dates are left null because the provider does not return them.
    - A finding counts as a `verified_fact` only when one of its cited URLs appears in the returned `sources`. Otherwise it is downgraded to `analysis` and flagged `unverified_citation`.
- **DuckDB.** A new `research` schema holds `research_runs`, `research_sources` and `research_findings`.
  - It is kept separate from `raw.signals`.
  - It is created at API startup, so existing warehouses pick it up without reseeding.
  - At startup, runs left in progress are marked `failed: interrupted`.
- **API.** New endpoints:
  - `POST /research` (202, background task)
  - `GET /research`
  - `GET /research/{id}`
  - `GET /research/{id}/sources`
  - `GET /research/{id}/findings`
  - `GET /findings` (feed with category, kind and demo filters)
  - `GET /findings/categories`
  - `GET /research/config`
  - Status values are `queued`, `running`, `completed`, `partial` and `failed`.
  - No agent steps are invented.
- **Frontend.**
  - New pages: Research workspace, Research report (Report, Findings and Sources tabs), and Intelligence feed.
  - The Overview gained "Important developments" and "Recent research".
  - Competitors is renamed to Companies.
  - Navigation and branding were updated.
  - A run's page polls every 3 s, and only while it is queued or running.
- **Demo.**
  - The AI-company seed is replaced by 7 Indian EV and battery companies. All their signals are labelled `[Sample]` and link only to the company's real home page.
  - A demo research snapshot (`is_demo`) is shown with a "Demo snapshot" badge. Its findings are all analysis, never facts.
  - The pricing mart now parses ₹/INR.
  - The static export now includes research data.
- **Tests.** 12 new tests in `tests/test_research.py`. The provider is mocked with `httpx.MockTransport`, so they need no network and use no credits.

## Quality gates (latest run)

| Gate | Result |
|---|---|
| `uv run pytest` | 53 passed |
| `npx tsc --noEmit` (web) | clean |
| `next build` | success; all routes prerender, including `/research`, `/research/view` and `/feed` |
| `GET /health` | `{"status":"ok"}` |
| Research without a key | run stored as `failed / missing_key` with a readable message; API stays up |
| Research with a mocked provider (tests) | completed; stored in DuckDB; shown in the feed |
| **Live Context.dev run** | **NOT YET VERIFIED: needs `CONTEXT_DEV_API_KEY`** |

## Commands

```powershell
cd compete
copy .env.example .env        # then set CONTEXT_DEV_API_KEY=...
uv sync --extra dev --extra dbt --extra api --extra report
$env:PYTHONUTF8=1; uv run python scripts/seed_demo.py --build   # API must be stopped (DuckDB lock)
uv run uvicorn api.main:app --port 8000
# second terminal:
cd web; npm ci
"NEXT_PUBLIC_STATIC_DATA=0" | Out-File -Encoding ascii .env.local   # talk to the live API
npm run dev                    # http://localhost:3000/dashboard
```

To capture a live run for the offline/static build, stop the API and run `uv run python scripts/export_static_data.py`.

## Known limitations

- The Context.dev Answers API returns `sources` as bare URLs. Titles and snippets appear only when the Search API returns the same URL, so many sources show the domain only. Publication dates are not available.
- Research is a single non-streaming provider call, so the UI shows the real backend status (queued, then running, then done), not step-by-step progress.
- Background work uses FastAPI `BackgroundTasks` (in-process). If the API restarts mid-run, that run is marked failed (interrupted).
- The key is read fresh from `.env` on every request. Free-tier limits are 10 requests per minute and 2 concurrent.
- The static (server-less) build can show stored runs but cannot start new research.
- Findings are not deduplicated across runs.

## Remaining work

- Run one live research with a real key, then confirm the sources and findings.
- Optionally run `export_static_data.py` so the static build carries the live snapshot.
