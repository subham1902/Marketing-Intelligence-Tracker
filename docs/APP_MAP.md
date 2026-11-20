# App map (source of truth for the in-app guide)

Every guide answer must match this file, and this file must match the code.

## Pages (Next.js routes, `web/src/app`)

| Route | Nav label | What it shows | Main actions |
|---|---|---|---|
| `/` | — | Redirects to `/dashboard` | — |
| `/dashboard` | Overview | Stat cards (companies tracked, signals this week, high significance, active alerts); "Latest live developments" (live findings, verified first); "Recent research"; "Market pulse" (findings by category); signals by type; recent signals; weekly activity chart | Run pipeline; Intelligence feed link; New research link |
| `/research` | Research | Research workspace form and the list of research runs | Templates (Market overview, Policy & incentives, Tenders & procurement, Competitor moves); objective, industry, geography, time window, source preferences; "Focus on tracked companies"; **Run research**; "Connect LLM for AI summaries" link |
| `/research/view?id=…` | (Research) | One research report: status, stage bar while running, then the Report, Findings and Sources tabs | Switch tabs; Open source (external link); Open report from findings |
| `/feed` | Feed | Findings from every run, newest first | Category chips (10 categories); kind chips (Provider-cited fact, Source-supported (quote verified), Source excerpt, Analysis); "Include demo snapshot" checkbox; Open report |
| `/competitors` | Companies | Tracked companies with signal counts | Open a company |
| `/competitors/{id}` | (Companies) | Company profile: Live developments (from free public sources), pricing history chart, hiring by location, content cadence, Sample signals (demo seed) | **Refresh news**; Open run |
| `/signals` | Signals | Extracted signals for tracked companies (sample seed data) | Filters |
| `/changes` | Changes | Every detected change, filterable and sortable | Filters |
| `/reports` | Reports | Auto-generated weekly briefs (demo) with PDF | Open / PDF |
| `/settings` | Settings | Manage companies (add/edit/delete), alerts, appearance | Add company; Edit; Delete |

## Global UI

- **Sidebar nav:** Overview, Research, Feed, Companies, Signals, Changes, Reports, Settings. The mobile bottom bar shows Overview, Research, Feed, Companies and Reports.
- **Top bar:** "Jump to…" (Ctrl+K command palette), **Connect LLM** / "AI summaries on" button, theme toggle.
- **Ctrl+K palette:** pages (Overview, New research, Intelligence feed, Companies, Weekly reports, Settings), every company, and the latest 15 research runs.
- **Connect LLM panel:** modes *Off: cited extracts* (default), *Local model (Ollama)*, *API key* (presets OpenAI, Groq, Gemini, OpenRouter, custom). **Test** and **Save and connect**. The key is stored server-side only.

## Provenance labels

| Label | Meaning |
|---|---|
| Source excerpt | Verbatim text from the source page, no generated prose (extractive mode) |
| Source-supported (quote verified) | AI finding whose evidence quote was found word for word in the cited source |
| Provider-cited fact | Context.dev said a source supports it; not independently verified |
| Analysis | Interpretation, or a citation that could not be verified (flags: quote not found, citation unverified) |
| Outside time window | Dated before the run's window; shown as background |
| Covered by N sources | The same story from several publishers, merged |
| Demo snapshot / [Sample] | Preloaded sample data, never live |
| Live · free public sources | A real run via the open provider |

## Research run lifecycle

The statuses are queued, running, completed, partial and failed.

The open provider reports its real stage as it goes:
1. Discovering sources (DuckDuckGo news, Google News, PIB, GDELT)
2. Fetching N sources
3. Synthesizing (extractive mode or AI)
4. Done

A failed run shows a readable reason. For example, `no_sources` means no relevant articles were found for the window.

## API (FastAPI; every route is also served under `/api`)

- **Health:** `GET /health`
- **Overview:** `GET /stats/overview`
- **Companies:**
  - `GET/POST /competitors`
  - `GET/PATCH/DELETE /competitors/{id}`
  - `/competitors/{id}/pricing-history`, `/hiring`, `/cadence`
- **Feeds:** `GET /signals`, `GET /changes`
- **Reports:** `GET /reports`, `GET /reports/{id}`, `/reports/{id}/pdf`
- **Pipeline:** `POST /pipeline/run`
- **Research:**
  - `GET /research/config`
  - `POST /research`, `GET /research`
  - `GET /research/{id}`, `/research/{id}/sources`, `/research/{id}/findings`
- **Findings:** `GET /findings` (feed), `GET /findings/categories`
- **Company news:** `POST /companies/{id}/refresh`, `GET /companies/{id}/developments`
- **AI summaries:** `GET/PUT /settings/llm`, `POST /settings/llm/test`
- **Guide:** `POST /assistant/chat`

## Known limits (state them honestly)

- **GDELT** is often rate-limited and covers only about 3 months.
- **Google News links** are aggregator redirects.
- **Some government pages** have no date, which shows as "Not available".
- **Hosted (Emergent) storage** may be ephemeral, so new runs can be lost on redeploy.
- **AI-written prose** is not quote-verified.
- **Not built:** scheduled monitoring, alerts delivery, multi-user accounts and predictive analytics.
