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
    - The fact / analysis label comes from the provider, so it is shown as "Provider-cited fact", not as independently verified. Context.dev appends every URL cited in its answer to `sources`, so a URL being in `sources` proves nothing on its own.
    - Each returned URL gets a reachability check (8 s timeout, redirects followed): `ok`, `dead` (404, 410 or connection/DNS failure) or `unknown` (403, 429, 5xx or timeout; government sites often block bots).
    - A "fact" whose cited links are all `dead` is downgraded to analysis and flagged `dead_citation`. A "fact" with no cited source is downgraded and flagged `unverified_citation`.
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
- **Tests.** 14 new tests in `tests/test_research.py`. The provider is mocked with `httpx.MockTransport`, so they need no network and use no credits.

## Quality gates (latest run)

| Gate | Result |
|---|---|
| `uv run pytest` | 55 passed |
| `npx tsc --noEmit` (web) | clean |
| `next build` | success; all routes prerender, including `/research`, `/research/view` and `/feed` |
| `GET /health` | `{"status":"ok"}` |
| Research without a key | run stored as `failed / missing_key` with a readable message; API stays up |
| Research with a mocked provider (tests) | completed; stored in DuckDB; shown in the feed |
| Live Context.dev run | Verified: narrow query completed (1 finding, 2 sources); full EV objective completed at a 300 s deadline (4 provider-cited findings, 4 reachable pib.gov.in sources). The 180 s default returned partial. |

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

## Recommended demo sequence (about 5 minutes)

1. **Overview** (`/dashboard`): companies tracked, important developments, recent research runs. Point out the "Demo snapshot" badges.
2. **Companies**: open Ather Energy to show tracked URLs, change signals, the INR pricing chart and hiring. All of these are labelled `[Sample]`.
3. **Research**: the example EV objective is prefilled. Set the time window to 6 months, keep Company announcements, Government and Tenders selected, then click **Run research**.
4. The report page shows **Queued**, then **Researching**. It polls the real backend status every 3 s; a run takes about 30-180 s.
5. **Report** tab: executive summary, overview, then sections covering trends, launches, manufacturing, partnerships, policy, tenders, opportunities and risks.
6. **Findings** tab: category, provider-cited fact vs analysis, significance, confidence and clickable source domains.
7. **Sources** tab: domain, type (government, tender, company, news, web), link-check status and **Open source**.
8. **Feed**: filter by Policy or Tender, and toggle "Include demo snapshot" off so only live findings remain.
9. Revisit the run from the Research list. It loads from DuckDB without another API call.
10. Failure handling: show a failed run (for example, without a key the run is stored as `missing_key` with a readable error).

## Known limitations

- The Context.dev Answers API returns `sources` as bare URLs. Titles and snippets appear only when the Search API returns the same URL, so many sources show the domain only. Publication dates are not available.
- Research is a single non-streaming provider call, so the UI shows the real backend status (queued, then running, then done), not step-by-step progress.
- Background work uses FastAPI `BackgroundTasks` (in-process). If the API restarts mid-run, that run is marked failed (interrupted).
- The key is read fresh from `.env` on every request. Free-tier limits are 10 requests per minute and 2 concurrent.
- The static (server-less) build can show stored runs but cannot start new research.
- Findings are not deduplicated across runs.

## Remaining work

- Live research verified. Use COMPETE_RESEARCH_TIMEOUT=300 for broad objectives.
- Optionally run `export_static_data.py` so the static build carries the live snapshot.

## Release hardening (20 Nov 2026)

- Re-verified on HEAD `74a205f`: `uv run pytest` 56 passed (the log above predates the retry/backoff commit).
- **Link check fix** (`pipeline/research/service.py`): TLS/certificate failures were raised by httpcore as `ConnectError` and so classified `dead`, which downgraded real citations to analysis with `dead_citation`. TLS failures are now `unknown`; only genuine DNS/connection failures are `dead`.
- **Source type fix**: `sebi.gov.in` was classified `government` because the `.gov.in` rule ran first. Regulators are now checked before the generic government rule.
- 3 new tests in `tests/test_research.py`. `uv run pytest`: 59 passed (also re-run on Windows; `tsc --noEmit` clean and `npm run build` succeeds).

## Display fixes (20 Nov 2026)

- Pricing chart used a hardcoded USD formatter; it now uses the currency carried by the data (INR shows as ₹ with Indian digit grouping, e.g. ₹1,20,000).
- Company page breadcrumb renamed from "Competitors" to "Companies".
- Findings dated before the run's time window are flagged `outside_window` and shown with an "Outside time window" badge. They are flagged, not hidden. Stored runs are backfilled at API startup. 1 new test; `uv run pytest`: 60 passed; `tsc` clean; `npm run build` succeeds.

## Overnight build (20 Nov 2026, 01:46-05:10 IST)

Spec: `docs/OVERNIGHT_BUILD_PROMPT.md`. Progress per phase is in `PROGRESS.md`; the summary is in `MORNING_REPORT.md`.

- **Phase 1:** baseline green. Added dependency `ddgs` 9.16.1 (pre-approved). Ollama models: qwen2.5:7b-instruct (pulled tonight), qwen3.5:9b, qwen3.5:4b.
- **Phase 2:** free `open` provider (default), real status stages, new kinds `source_excerpt` / `source_supported`, columns `evidence_quote`, `discovered_via`, `status_message` (added with `ALTER ... IF NOT EXISTS`). 12 fixture tests.
- **Phase 3:** `POST /companies/{id}/refresh`, `GET /companies/{id}/developments`, and a Live developments card.
- **Phase 4:** real EV snapshot, `config/research_snapshot.json`, `/api` mirror, first-boot autoseed, `requirements.txt`.
- **Phase 5:** hosting defaults (frontend live mode, `COMPETE_LLM_PROVIDER=mock`), Emergent hand-off doc, README quick start.
- **Phase 6:** browser QA fixes: background polling, objective-driven discovery and ranking, verified-first ordering, a label on the unverified LLM summary.
- **Gates:** pytest 72 passed; tsc clean; `npm run build` success; `/api/health` ok.
- **Alternative not taken:** Emergent's universal LLM key for hosted summaries. It's a P0 idea in the hand-off doc and must keep the `quote_in_text` rule.
