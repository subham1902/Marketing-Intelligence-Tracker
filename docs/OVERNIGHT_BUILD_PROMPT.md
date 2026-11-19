# OVERNIGHT AUTONOMOUS BUILD — Market Intelligence Tracker

You are working unattended overnight. The user is asleep and will not answer questions.
**Make every decision yourself, never stop to ask, and keep going until the Definition of Done is met or the hard stop is reached.**

- Repo: this `compete` folder. Branch: `hackathon/market-intelligence`.
- Read first: the Master Project Charter (if present in the repo or docs), `IMPLEMENTATION_LOG.md`, `CLAUDE.md`, `README.md`.
- Hackathon deadline: **Friday 20 Nov 2026, 11:00 AM IST**.
- **Hard stop: 08:30 IST.** From 08:00, do only stabilisation, the final verification and the morning report. Check the clock (`Get-Date` / `date`) at the start of every phase.
- After the hackathon the user will import this repo into **Emergent** to enhance the UI. Keep it import-friendly: a standard structure, clear README run steps, `.env.example` complete, no hard-coded Windows paths.

---

## 0. Prime directive

**The app must work with zero paid services and zero credits.**

- **Context.dev:** stays as an *optional* provider. **Never call it live tonight**: no live `POST /research` with `provider=contextdev`. The quota is being protected.
- **Default research provider:** a new, free, open-source "open" provider (spec below).
- **Without any key:** the app must still run end to end, using free keyless sources plus an extractive (non-LLM) synthesis mode.
- **If a free local LLM is available (Ollama):** use it for better synthesis.
- **Gemini or Groq:** if the user has added a key to `.env`, use it as an optional free-tier path. Never require one.
- **Keep the existing working app alive at every commit.** Never leave the branch in a broken state.

---

## 1. Non-negotiable rules

1. **Do not:** reset, rebase, force-push, `git push`, or delete the repo or any folder outside the repo. Commit locally only.
2. **Never** print, log or commit `.env` or any key. `.env` is gitignored; keep it that way.
3. **Do not replace the stack:** Next.js 14, FastAPI, DuckDB, dbt. Add no new database, queue, vector store, agent framework or frontend framework.
4. **New Python dependencies:** only if free, open-source and pure-pip. Pre-approved: `ddgs`. Prefer existing ones: `httpx`, `feedparser`, `trafilatura`, `selectolax`, `instructor`, `openai` (for Ollama's OpenAI-compatible endpoint). Record every added dependency in the log.
5. **Do not fabricate:** sources, dates, quotes, figures or "verified" status. Missing means `null`, shown as "Not available". Keep and extend the provenance rules already in `pipeline/research/service.py`.
6. **Tests never hit the network.** Mock with `httpx.MockTransport` and fixtures (existing pattern in `tests/test_research.py`).
7. **Small steps.** After every phase: `uv run pytest`, then `cd web && npx tsc --noEmit && npm run build`. Commit only when both are green. Message format: `phase N: <what>`.
8. **If a step fails three times with different approaches:** revert that step (`git checkout -- <files>` or `git revert` your own commit), log it under "Skipped / needs human" in `MORNING_REPORT.md`, and move on. **Never get stuck. Never stop.**
9. **Windows:** use PowerShell-compatible commands and `$env:PYTHONUTF8=1`. Stop the API before reseeding or exporting (DuckDB file lock). Kill any dev servers you start before finishing.
10. **Be polite to free endpoints.**
    - Set a real User-Agent and timeouts.
    - Throttle: GDELT ≥ 5 s between calls; others ≥ 1–2 s.
    - Cache raw responses on disk under `data/research_cache/` (gitignored), so re-runs don't re-hit sources.
11. **Keep `PROGRESS.md` updated** (repo root, committed) after each phase: phase, status, the next action. If your context gets compacted or the session restarts, re-read `PROGRESS.md` and continue from there.

---

## 2. Phases (in order; each must end green and committed)

### Phase 1 — Baseline (≤ 20 min)

- `git status`, `git log --oneline -10`. Commit any pending work only if tests pass. Expected pending files: `service.py`, `test_research.py`, `IMPLEMENTATION_LOG.md`, which contain the TLS link-check and SEBI classification fixes.
- `uv sync --extra dev --extra dbt --extra api --extra report`. Run `pytest`, `tsc` and the build. Record the numbers in `PROGRESS.md`.
- Detect the free LLM:
  - Run `ollama list`.
    - If a model ≥ 7B is already pulled (prefer `qwen2.5`, `llama3.1`, `mistral`, `gemma2` instruct variants), use it.
    - If Ollama is installed but has no suitable model, run `ollama pull qwen2.5:7b-instruct`, in the background, while you continue.
    - If Ollama isn't installed, do not install system software. Use extractive mode and note it in the morning report.
  - Check `.env` for a non-empty `GOOGLE_API_KEY` / `GROQ_API_KEY` by name only, without printing values.

### Phase 2 — Free "open" research provider (the core of tonight)

Create `pipeline/research/open_provider.py` implementing the existing `ResearchProvider` protocol. That way the service, store, API and UI keep working unchanged.

Select it via `COMPETE_RESEARCH_PROVIDER=open|contextdev` (default `open`). Add it to `.env.example`, `GET /research/config`, and show it in the UI.

#### Step 1 — Discover (all free, no key)

Turn the request (objective, industry, geography, companies, time window) into 4–8 focused queries, e.g. `"electric vehicle" India`, `<company> EV`, `FAME OR "PM E-DRIVE" OR PLI EV`, `EV charging tender India`.

| Source | Endpoint and notes |
|---|---|
| **GDELT DOC 2.0** | `https://api.gdeltproject.org/api/v2/doc/doc?query=<q> sourcecountry:IN sourcelang:english&mode=ArtList&format=json&maxrecords=75&timespan=<1m/3m>&sort=DateDesc`<br>No key. Its rolling window is about 3 months, so for 6m/12m requests say so in the report instead of pretending.<br>Map `seendate` to the source's `published_at` (labelled "first seen by GDELT"). Guard against non-JSON error bodies. |
| **Google News RSS** (via `feedparser`) | `https://news.google.com/rss/search?q=<q>+when:<N>d&hl=en-IN&gl=IN&ceid=IN:en`<br>Gives title, publisher, `pubDate`. Links are Google redirect URLs: try to resolve them to the publisher URL (follow redirects). If resolution fails, keep the article but mark the URL as an aggregator link. |
| **PIB official press releases** (via `feedparser`) | `https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3` (English).<br>Filter items by keyword relevance. This is the official government source. If the English params fail, probe `https://www.pib.gov.in/ViewRss.aspx` for the right feed URL. |
| **DuckDuckGo / metasearch** (`ddgs` package) | `DDGS().text(q, region="in-en", max_results=10)` and `.news(...)`.<br>Use for company press pages and `site:gem.gov.in OR site:eprocure.gov.in` tender discovery.<br>Wrap in try/except: it is unofficial and may rate-limit. Never fail the run because of it. |
| **Tenders** | Probe `https://gem.gov.in/cppp` (paginated, public CPPP mirror; check for a keyword/search parameter).<br>If there is no search parameter, scan only the first few newest pages and keyword-filter (electric vehicle, EV, e-bus, charging, battery, lithium).<br>`eprocure.gov.in` search uses a CAPTCHA: **do not try to bypass it.**<br>If tenders can't be fetched reliably, rely on ddgs/news discovery. Label the section honestly: "Tender items discovered via search; not a live portal integration". |

#### Step 2 — Fetch and extract

- Deduplicate by normalized URL (reuse `_norm_url`). Rank: official/government first, then company domains (from `config/competitors.yaml`), then news. Cap at about 25 pages per run.
- Fetch with `httpx`, extract the main text with `trafilatura` (already a dependency), and get the publish date from `trafilatura` metadata when available.
- Store the source title, real snippet (first relevant sentences) and date. This removes the old "Answers returns bare URLs" limitation.

#### Step 3 — Synthesize. Two modes, auto-selected:

1. **LLM mode** (Ollama, or Gemini/Groq if a key is set; reuse the client setup in `pipeline/extract/llm.py`).
   - Give the model numbered source excerpts. Require JSON matching the existing `JSON_FORMAT` (report sections plus findings).
   - Each finding must cite source numbers **and an `evidence_quote` copied from that source**.
   - Validate in code:
     - If the quote, after whitespace/case normalization, occurs in the cited source's extracted text, the finding is `kind="source_supported"`.
     - If not, downgrade it to `analysis` with flag `quote_not_found`.
   - Chunk the inputs to fit a 7B model's context (about 6–8k tokens).
   - If the model returns invalid JSON twice, fall back to extractive mode for that run.
2. **Extractive mode** (no LLM at all).
   - Each relevant article becomes a finding: title = headline; summary = the extracted lead sentences (verbatim, quoted); category from keyword rules (reuse/adapt the mock extractor's keyword lists); entity = the matched company name; date = the article date.
   - `kind="source_excerpt"`.
   - Report sections are bullet lists of these findings grouped by category. The executive summary is a templated count summary: "N developments from M sources across …".
   - **No invented prose.**

#### Labels and data

- Keep the existing labels for Context.dev: "Provider-cited fact" / "Analysis".
- Add **"Source-supported (quote verified)"** and **"Source excerpt"** for the open provider.
- Update the frontend badge components and the feed `kind` filter to match.
- If the schema needs new columns (e.g. `evidence_quote`, `published_at_source`), add them with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` at startup, following the existing `research_store` init pattern. Existing warehouses must keep working without reseeding.
- **Run status:** report real stages in the run's status message (Discovering → Fetching N sources → Synthesizing → Done). This is honest progress, since these are real steps. Show it on the run page.

#### Tests

Use fixtures for GDELT JSON (including a non-JSON error body), Google News RSS XML, PIB RSS XML and a sample HTML page. Cover:
- the quote-verification pass and fail paths
- the extractive mode
- the fallback from LLM to extractive
- that `ddgs` failure doesn't fail the run

**Live smoke test** (allowed: free sources only): run one narrow open-provider research run through the API (e.g. "Ather Energy developments India", window 1m), with whichever synthesis mode is available. Confirm sources have real titles and dates and that the report renders. Record the result in `PROGRESS.md`.

### Phase 3 — Company intelligence uses real data (free)

- Add a "Refresh news" action per company. It runs the open provider's discovery for that company name over the last month and stores the results as research findings linked to the company (`entity`). Endpoint: `POST /companies/{id}/refresh` or reuse `/research` with `companies=[name]`.
- **Do not overwrite or relabel the `[Sample]` seed signals.** They stay explicitly labelled sample data.
- The company page shows "Live developments (from free public sources)" separately from "Sample signals".
- Wire the existing collectors (static/RSS/trafilatura) to actually run against each company's tracked homepage/newsroom URLs, if they already work offline. Respect `robots.txt` (the setting already exists). Skip any source that blocks access, and log it.

### Phase 4 — Capture a real demo snapshot

- With the API running, execute one **broad** open-provider run with the charter's example EV objective (window 3m, since GDELT's window is limited).
- Mark it `is_demo=false` (it is real). Keep the old demo snapshot clearly badged.
- Stop the API, run `uv run python scripts/export_static_data.py`, so the static build and Emergent import carry real data.
- Note in `MORNING_REPORT.md` the run id, the number of sources, the share of government vs company vs news sources, and how many findings were source-supported vs analysis.

### Phase 5 — Product polish (only what makes the 5-minute demo stronger)

- Research report: source cards with title, domain, type badge, date ("Not available" when missing), snippet and an Open button. Each finding links to its cited source cards. Show the evidence quote under each source-supported finding.
- Dashboard: real counts from DuckDB; "Latest live developments" from open-provider findings.
- Clear empty, loading and error states on every page. Run failures show a human-readable reason.
- Responsive check at 1280px and 390px widths.
- Keep the existing design system (Tailwind, shadcn, Tremor). No redesign tonight; Emergent will do that.
- **Do not add new features beyond this list.**

### Phase 6 — Browser QA (real clicks, not just builds)

Start the API (port 8000) and web (`npm run dev`, port 3000, `NEXT_PUBLIC_STATIC_DATA=0`). Use Playwright, already a dependency (`uv run playwright install chromium` if needed). Script and run the full journey:

1. Dashboard
2. Companies
3. Company profile
4. Refresh news
5. Research workspace
6. Start an open-provider run (narrow query)
7. Watch the status change
8. Report tab
9. Findings tab
10. Sources tab: open a source
11. Feed: filter by category/kind, toggle demo off
12. Reopen a saved run (no new provider call)
13. Failure case: force a provider error (e.g. set `COMPETE_RESEARCH_PROVIDER=contextdev` with no key, in a test env only) and check the readable error

Save screenshots to `docs/qa/` and fix any console errors or broken interactions you find. Commit the Playwright script as `scripts/qa_journey.py` so it can be re-run.

### Phase 7 — Hand-off (must finish by 08:30)

- **`README.md`:** a "Quick start (free, no keys)" section with Windows PowerShell commands, plus the optional Ollama and optional Context.dev/Gemini/Groq setup. Keep the upstream attribution.
- **`IMPLEMENTATION_LOG.md`:** append everything done tonight, with the final test count and the gates table.
- **`docs/EMERGENT_HANDOFF.md`:**
  - the architecture in brief (two intelligence paths, provider abstraction, DuckDB schemas)
  - the files Emergent must not break (provider, service, store, routers, the DuckDB schema)
  - a suggested prompt for Emergent: "audit then enhance the UI only; do not replace the backend or data model"
  - P0/P1 enhancement ideas from the charter
- **`MORNING_REPORT.md`** (repo root, at most 1 page). Sections:
  - **Status:** working or not.
  - **How to start it:** exactly 3 commands.
  - **What was built tonight:** bullets.
  - **Verified:** each gate with its actual result.
  - **Not verified / known limitations:** honest list.
  - **Skipped / needs human:** only items that truly need the user (e.g. "install Ollama", "add a free GROQ_API_KEY for better summaries"), each with the exact one-line action.
  - **Suggested 5-minute demo script.**
- **Final gates:** `pytest` green, `tsc` clean, `npm run build` success, `/health` ok. Final commit: `overnight build complete`. Stop all servers you started.

---

## 3. Decision rules when unsure

Prefer, in this order:
1. Works reliably in the demo
2. Honest labelling
3. Free and no key
4. Reuse of existing code
5. Fewer moving parts
6. Visual polish

When a free source is flaky, degrade gracefully and label it; never block a run on one source.

When two approaches tie, pick the one with less code and note the alternative in the log.

## 4. Definition of Done

- `uv run pytest` green; `npx tsc --noEmit` clean; `npm run build` succeeds.
- **With no keys at all** (empty `.env` apart from defaults): a user can run research from the UI and get a report with real, dated, linked sources and labelled findings.
- With Ollama available, the same run produces LLM-written sections whose findings carry verified quotes.
- The company page shows live free-source developments, separate from `[Sample]` data.
- The demo snapshot is real and exported; the old demo data stays clearly badged.
- `MORNING_REPORT.md`, `docs/EMERGENT_HANDOFF.md` and the README quick start exist and are accurate.
- Every claim in `MORNING_REPORT.md` was actually run and observed tonight.

Begin now with Phase 1. Do not ask for confirmation.
