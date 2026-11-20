# Release report: Market Intelligence Tracker (hackathon MVP)

**Repo:** https://github.com/subham1902/Marketing-Intelligence-Tracker (public; default branch `main`, plus `hackathon/market-intelligence`)

Built on [yassnemo/compete](https://github.com/yassnemo/compete) (MIT). The `LICENSE` is unchanged.

## What was added in this release

- **Guide assistant ("Volt")**
  - A three.js companion in a floating launcher; Ctrl+/ or *Ask the guide* in Ctrl+K.
  - It answers from `config/app_guide.yaml` (37 entries built from `docs/APP_MAP.md`) using BM25 with a page boost.
  - It reads live run status, feed counts and company count from DuckDB, and explains "what just happened" from the activity log.
  - When it isn't confident it says so and offers close topics instead of guessing.
  - Answers stream word by word, with actions, suggestions, Stop, Copy, New chat and per-page starter chips.
  - It works with no LLM. A connected LLM can optionally rephrase answers, staying within the retrieved entries.
- **Transparency:**
  - A 2 px activity bar (queries, mutations and route changes) and a reading-progress bar.
  - An **Activity** drawer listing every API call (plain label, status, duration, error), navigation, key actions and research stage changes, with filters and Clear.
  - Toasts only when long tasks complete or fail.
- **Connect LLM panel:** Off (default, cited extracts), Ollama, or an OpenAI-compatible key, with Test and Save. The key stays server-side.
- **New logo** (from the supplied reference) and the grid-map theme.
- **Usability fixes:** 6 issues fixed (hydration error, stale stage spinners, mobile launcher overlap, toast placement, noisy toasts, label casing). See `docs/USABILITY_REPORT.md`.

## Library decisions

- **`streamdown@2.8.0`** (Apache-2.0) renders guide messages. Its peer dependency is React ^18 || ^19, so it works on React 18.3.1 with no upgrade. It provides the animated word reveal (`blurIn`) and a streaming caret.
- **`three@0.187.0`** (MIT) for the guide bot. It's lazily imported, falls back gracefully without WebGL, and holds still under reduced motion.
- **assistant-ui, the Vercel AI SDK and chat kits** were not used. The backend streams plain text, which is read with `fetch` and a `ReadableStream`.
- **No new state library.** The activity tracker is a React context and reducer.

## Gates

| Gate | Result |
|---|---|
| `uv run pytest` | 94 passed |
| `npx tsc --noEmit` | clean |
| `next lint` | no warnings or errors |
| `npm run build` | success |
| `/api/health` | ok |

## Usability findings

6 fixed; 1 open by design (a full page reload isn't logged as navigation); 2 informational. Details are in `docs/USABILITY_REPORT.md`.

## Secret scan (full history, counts only)

- Known `.env` secret values found in history: **0**.
- Pattern matches (`sk-`, `AIza`, `gsk_`, `ghp_`, `github_pat_`, `xox`, private keys, `ctxt_secret`, assigned high-entropy secrets): **0**.
- Forbidden tracked files (`.env`, `data/`, `*.duckdb`, `*.parquet`): **0**. Files over 50 MB: **0**.
- `GET /repos/.../contents/.env` on GitHub returns **404**.

## Manual steps

- **Rotate the Context.dev key** at https://www.context.dev/dashboard/api-keys. It was pasted in chat earlier. It is not in the repo, but rotate it anyway.
- **Emergent:** connect it to this GitHub repo and follow `docs/EMERGENT_HANDOFF.md`. The backend is `cd backend && pip install -r requirements.txt && uvicorn server:app --port 8001`; the frontend is `web/`.
- **Scripted QA** (`scripts/qa_journey.py`) needs `playwright install` on a machine without the local hook.

## Demo the guide and Activity in 60 seconds

1. Click **Ask the guide** (bottom-right bot) and tap the starter chip *How do I run research?*. Watch the answer stream, then click **Open Research**.
2. Open a company (Ctrl+K → "TVS") and click **Refresh news**. The top activity bar runs and the stage bar fills.
3. Open **Activity** (pulse icon in the top bar) to see the real stages: Discovering → Fetching → Synthesizing → completed.
4. Ask the guide *"what's the status of my research?"* and then *"what just happened?"*. Both answers come from live data.
5. Ask something off-topic to show the guide admits when it doesn't know.
