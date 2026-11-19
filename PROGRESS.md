# Overnight build progress

Spec: `docs/OVERNIGHT_BUILD_PROMPT.md`. Hard stop: 08:30 IST, 20 Nov 2026.

| Phase | Status | Notes |
|---|---|---|
| 1 Baseline | done (01:50 IST) | pytest 60 passed; tsc clean and build OK at HEAD 3a7d885. Added `ddgs` 9.16.1. Ollama 0.40.11 is installed with only `qwen3.5:4b`, so `qwen2.5:7b-instruct` is being pulled in the background. No Gemini/Groq keys. |
| 2 Open provider | done (02:25 IST) | `pipeline/research/open_provider.py`, default `COMPETE_RESEARCH_PROVIDER=open`. Sources: ddgs news (works), Google News RSS (works; links are aggregator redirects, labelled), PIB RSS (redirects to the Hindi feed; English + keyword filter), GDELT (rate-limit/unreachable from this network; guarded). Live smoke `rr-20261119-17dabf9c` (Ather, 1m): completed, 25 sources, all titled and dated, extractive. LLM path (qwen3.5:9b via native Ollama API, think off, num_ctx 8192): 6 findings, all quotes verified, 77 s. pytest 71 passed. |
| 3 Company refresh | pending | |
| 4 Real snapshot | pending | |
| 5 Polish | pending | |
| 6 Browser QA | pending | |
| 7 Hand-off | pending | |

**Next action:** Phase 2, `pipeline/research/open_provider.py`.
