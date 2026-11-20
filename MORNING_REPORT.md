# Morning report: 20 Nov 2026

## Status: working ✅
Research now runs on **free public sources with no keys**. The app is ready for Emergent hosting:
- every API route is also served under `/api`
- first boot seeds demo data, builds the marts and loads real captured runs
- Python dependencies are in `requirements.txt`

All tests pass, the typecheck is clean and the production build succeeds.

## How to start it (3 commands)
```powershell
uv sync --extra dev --extra dbt --extra api --extra report
uv run uvicorn api.main:app --port 8000
cd web; npm install; npm run dev
```
Then open http://localhost:3000. For Emergent, follow `docs/EMERGENT_HANDOFF.md` (backend on port 8001, `pip install -r requirements.txt`).

## What was built tonight
- **Free "open" research provider** (`pipeline/research/open_provider.py`):
  - Discovers articles via DuckDuckGo news, Google News RSS, PIB press releases and GDELT, fetches each page and extracts its text and date with trafilatura.
  - Synthesis is **extractive** (verbatim, no generated prose) or **local LLM**. In LLM mode a finding counts as "source-supported" only when its quote is found verbatim in the cited source.
  - This is now the default (`COMPETE_RESEARCH_PROVIDER=open`). Context.dev stays optional and was not called tonight.
- **Real progress stages** on the run page: Discovering → Fetching N sources → Synthesizing → Done.
- **Refresh news** on each company page: 1-month free-source research shown as "Live developments", separate from the `[Sample]` seed signals.
- **Real EV snapshot**: `rr-20261120-f3edb787`, committed in `config/research_snapshot.json` together with 3 other real runs.
- **Hosting readiness:**
  - `/api` mirror for every route
  - first-boot autoseed, tested on an empty database
  - keyless defaults
  - live-backend frontend by default
  - `requirements.txt`
- **Provenance labels**: Source excerpt, Source-supported (quote verified), Provider-cited fact, Analysis, Demo snapshot.
- **Docs**: README quick start and `docs/EMERGENT_HANDOFF.md`, which includes a suggested prompt for Emergent.

## Verified (observed tonight)
| Gate | Result |
|---|---|
| `uv run pytest` | 72 passed |
| `npx tsc --noEmit` | clean |
| `npm run build` | success |
| `/health` and `/api/health` | ok |
| Fresh empty DB boot | dbt OK; 7 companies, 4 real runs + demo, 64 feed findings |
| Broad EV snapshot (3m) | 25 sources: 6 government, 2 company, 17 news. 24 findings: 4 source-supported, 19 excerpts, 1 analysis |
| UI-started run (Ola Electric) | stages shown live; completed with 25 sources and 24 findings |
| Extractive mode (how Emergent will run) | Ola query: 25 sources, top 5 all about Ola, 51 s |
| Company Refresh news (Tata Motors) | 4 source-supported findings |
| Browser click-through | all journey steps passed (built-in browser) |

## Not verified / known limitations
- **Playwright journey not run:** `scripts/qa_journey.py` couldn't run here because a local hook blocks browser automation from the shell. The same journey was clicked manually instead.
- **GDELT** was rate-limited or unreachable from this network every time; the app guards it and notes it in the report.
- **Google News links** are aggregator redirects that can't be resolved server-side, so they're labelled "aggregator link".
- **PIB's RSS** serves mostly Hindi items. I filter for English titles, and PIB pages also come in through DuckDuckGo search.
- **Local LLM prose** (summaries and section text) is **not** quote-verified, and a 7B model got a company relationship wrong. The UI labels this text. On Emergent there's no local LLM, so reports are extractive.
- **Data persistence:** if Emergent's container storage is ephemeral, new research runs are lost on redeploy. The committed snapshot reloads each time.
- **Not done:** wiring the static collectors to company homepages (optional), and refreshing the static `/api-static` export (static mode is no longer the default).

## Skipped / needs human
- **Emergent:** import the repo, then run the backend with `pip install -r requirements.txt && uvicorn api.main:app --host 0.0.0.0 --port 8001` and the frontend with `cd web && npm install && npm run dev -- -p 3000`.
- **Rotate the Context.dev key** at https://www.context.dev/dashboard/api-keys. It was pasted in chat.

## Suggested 5-minute demo
1. **Overview:** latest live developments with provenance badges, and recent runs.
2. **Companies → Tata Motors:** click **Refresh news** and watch the stage, then show the live developments next to the `[Sample]` signals.
3. **Research:** type "Ola Electric developments in India" and click Run. The stages appear live (about 1 minute).
4. **Report:** findings with "Source excerpt" and quote-verified labels; sources with type, date and **Open source**.
5. **Open the broad EV snapshot:** government (PIB) sources and tender/policy findings.
6. **Feed:** filter to Policy, turn off "Include demo snapshot", and switch kinds.
7. Close on the message: free, keyless and honest. Nothing is invented, and every claim links to its source.
