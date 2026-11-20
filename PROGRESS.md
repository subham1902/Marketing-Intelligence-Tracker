# Overnight build progress

Spec: `docs/OVERNIGHT_BUILD_PROMPT.md`. Hard stop: 08:30 IST, 20 Nov 2026.

| Phase | Status | Notes |
|---|---|---|
| 1 Baseline | done (01:50 IST) | pytest 60 passed; tsc clean and build OK at HEAD 3a7d885. Added `ddgs` 9.16.1. Ollama 0.40.11 is installed with only `qwen3.5:4b`, so `qwen2.5:7b-instruct` is being pulled in the background. No Gemini/Groq keys. |
| 2 Open provider | done (02:25 IST) | `pipeline/research/open_provider.py`, default `COMPETE_RESEARCH_PROVIDER=open`. Sources: ddgs news (works), Google News RSS (works; links are aggregator redirects, labelled), PIB RSS (redirects to the Hindi feed; English + keyword filter), GDELT (rate-limit/unreachable from this network; guarded). Live smoke `rr-20261119-17dabf9c` (Ather, 1m): completed, 25 sources, all titled and dated, extractive. LLM path (qwen3.5:9b via native Ollama API, think off, num_ctx 8192): 6 findings, all quotes verified, 77 s. pytest 71 passed. |
| 3 Company refresh | done (04:35 IST) | `POST /companies/{id}/refresh` + `GET /companies/{id}/developments`; company page shows "Live developments (from free public sources)" apart from "Sample signals (demo seed)". Live: Tata Motors refresh -> 4 source-supported findings. Collector wiring skipped (optional; refresh covers it). pytest 72. |
| 4 Real snapshot | done | Broad EV run `rr-20261120-f3edb787` (3m, qwen2.5:7b): 25 sources (6 government, 2 company, 17 news), 24 findings (4 source-supported, 19 source excerpts, 1 analysis). Uncited sources kept as excerpts. Real runs exported to `config/research_snapshot.json` and loaded on first boot. Hosting: every route also under `/api/*`, first-boot autoseed (seed + dbt + snapshot) verified on an empty DB, `requirements.txt` added. |
| 5 Polish + hosting | done (04:52 IST) | Frontend defaults to live backend mode (`.env.development`/`.env.production` STATIC=0). Dashboard shows "Latest live developments" (no demo). Keyless defaults (`COMPETE_LLM_PROVIDER=mock`). `docs/EMERGENT_HANDOFF.md` and README quick start written. |
| 6 Browser QA | pending | |
| 7 Hand-off | pending | |

**Next action:** Emergent hand-off docs, then browser QA. The user will deploy on Emergent hosting: no Ollama there, so extractive mode is the hosted default.
