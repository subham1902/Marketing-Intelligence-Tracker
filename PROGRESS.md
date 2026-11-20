# Overnight build progress

Spec: `docs/OVERNIGHT_BUILD_PROMPT.md`. Hard stop: 08:30 IST, 20 Nov 2026.

| Phase | Status | Notes |
|---|---|---|
| 1 Baseline | done (01:50 IST) | pytest 60 passed; tsc clean and build OK at HEAD 3a7d885. Added `ddgs` 9.16.1. Ollama 0.40.11 is installed with only `qwen3.5:4b`, so `qwen2.5:7b-instruct` is being pulled in the background. No Gemini/Groq keys. |
| 2 Open provider | done (02:25 IST) | `pipeline/research/open_provider.py`, default `COMPETE_RESEARCH_PROVIDER=open`. Sources: ddgs news (works), Google News RSS (works; links are aggregator redirects, labelled), PIB RSS (redirects to the Hindi feed; English + keyword filter), GDELT (rate-limit/unreachable from this network; guarded). Live smoke `rr-20261119-17dabf9c` (Ather, 1m): completed, 25 sources, all titled and dated, extractive. LLM path (qwen3.5:9b via native Ollama API, think off, num_ctx 8192): 6 findings, all quotes verified, 77 s. pytest 71 passed. |
| 3 Company refresh | done (04:35 IST) | `POST /companies/{id}/refresh` + `GET /companies/{id}/developments`; company page shows "Live developments (from free public sources)" apart from "Sample signals (demo seed)". Live: Tata Motors refresh -> 4 source-supported findings. Collector wiring skipped (optional; refresh covers it). pytest 72. |
| 4 Real snapshot | done | Broad EV run `rr-20261120-f3edb787` (3m, qwen2.5:7b): 25 sources (6 government, 2 company, 17 news), 24 findings (4 source-supported, 19 source excerpts, 1 analysis). Uncited sources kept as excerpts. Real runs exported to `config/research_snapshot.json` and loaded on first boot. Hosting: every route also under `/api/*`, first-boot autoseed (seed + dbt + snapshot) verified on an empty DB, `requirements.txt` added. |
| 5 Polish + hosting | done (04:52 IST) | Frontend defaults to live backend mode (`.env.development`/`.env.production` STATIC=0). Dashboard shows "Latest live developments" (no demo). Keyless defaults (`COMPETE_LLM_PROVIDER=mock`). `docs/EMERGENT_HANDOFF.md` and README quick start written. |
| 6 Browser QA | done (05:03 IST) | A local hook blocks scripted browser automation from the shell, so `scripts/qa_journey.py` is committed but the journey was clicked in the built-in browser instead. Passed: dashboard, companies, company page and Refresh news (Tata: 4 findings), research workspace, UI-started run `rr-20261120-5c97da21` (Discovering -> Fetching 25 -> Synthesizing -> completed; 24 findings, 25 sources), report/findings/sources tabs, saved-run reopen, failed-run message. Fixed during QA: polling in background tabs, verified-first dashboard ordering, objective words now drive discovery and ranking (Ola query: top 5 all Ola), LLM summary labelled "not quote-verified" (the 7B model mixed up two companies). |
| 7 Hand-off | done (05:30 IST) | MORNING_REPORT.md (with future roadmap), docs/EMERGENT_HANDOFF.md, README quick start. Final gates green. |

**Next action:** MVP complete. Import into Emergent following docs/EMERGENT_HANDOFF.md; roadmap is in MORNING_REPORT.md.


## Afternoon release task (`docs/GUIDE_ASSISTANT_AND_RELEASE_PROMPT.md`)

| Phase | Status | Notes |
|---|---|---|
| A Baseline + app map | done | `docs/APP_MAP.md`; gates green |
| B Guide assistant | done | 37-entry KB, BM25 + status + activity, streaming endpoint, three.js "Volt" bot, Streamdown panel; 16 guide tests |
| C Transparency | done | Activity bar, reading bar, Activity drawer with central fetch instrumentation, stage logging, completion toasts |
| D Usability | done | `docs/USABILITY_REPORT.md`: 6 issues fixed; screenshots in `docs/qa/` |
| E Publish | done | Pushed to https://github.com/subham1902/Marketing-Intelligence-Tracker (public); history secret scan clean |

## Judging sprint (`docs/JUDGING_SPRINT_PROMPT.md`, hard stop 15:00 IST)

| Step | Status | Notes |
|---|---|---|
| 1 Baseline | done 13:05 | Clean, in sync with origin/main. LLM mode `off` (mock). The hook's `agents/context.md` does not exist. |
| 2 Marketing Analysis | done 13:20 | `pipeline/marketing/` (gather, signals, synth, service), `research.marketing_analyses`, `/marketing/analyses` (+`/api`), snapshot for 7 companies (rule-based, 30 sources each), `/marketing` UI, nav, Ctrl+K, profile button, 3 guide entries, 7 tests. pytest 101. |
| 3 Judge loop | done 14:43 | `/api/health` detail, `docs/DEPLOY_CHECKLIST.md`, `docs/PITCH.md`, `docs/JUDGE_SCORECARD.md`; extraction fixes (metric priority, money vs percent) |
| 4 Final | done | SPRINT_REPORT.md; gates green (101 tests); pushed |

## UI/UX upgrade (after sprint)

| Change | Notes |
|---|---|
| Aurora theme | Dark by default: indigo night, electric violet, mint and saffron; glass cards; aurora and dot backdrop; Tremor brand set to violet; light mode refreshed |
| Marketing insights | Key-takeaways hero (moat, pressure, tone, first move) and animated section reveal (reduced-motion safe) |
| Overview | Marketing Analysis spotlight card |
| Safety | AI recommendations never give buy/invest advice (filter, test, snapshot cleaned). pytest 102 |

## Retest and hardening pass

| Change | Notes |
|---|---|
| Full click-through | All 11 pages checked in the browser; mobile at 390 px has no horizontal scroll |
| Bug fix | Pages could stay invisible when JS animation frames were paused (background tab). Entrance motion is now CSS only |
| Theme | Calmer palette (lower saturation, softer glow and backdrop); one tonal headline gradient (an old lime rule was overriding it) |
| API hardening | Marketing runs: duplicate in-flight runs reused, max 3 concurrent (429), free-text names cleaned, 45 s gathering budget. pytest 103 |
| Copy | "1 linked source" pluralised correctly |
