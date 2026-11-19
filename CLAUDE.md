# Project conventions

## Context.dev (web research provider)

- **Env var:** `CONTEXT_DEV_API_KEY` in `compete/.env`. That file is gitignored. The key is server-side only: never put it in `web/` or in any `NEXT_PUBLIC_*` variable, and never log it.
  - Optional: `CONTEXT_DEV_MODE` (default `fast`), `CONTEXT_DEV_BASE_URL`, `COMPETE_RESEARCH_TIMEOUT`.
  - Use a timeout of 300 for broad objectives; 180 returned partial results.
- **Wrapper module:** `pipeline/research/provider.py` (`ContextDevProvider`, behind the `ResearchProvider` protocol). Every Context.dev call goes through it.
  - It uses raw HTTPX instead of the SDK, to stay on the existing dependency.
  - It retries a bounded number of times: on 429 it honours `Retry-After`, and on 408 or 5xx it backs off. Validation errors are never retried.
  - Errors are raised as `ProviderError(code=...)`.
- **Orchestration:** `pipeline/research/service.py` builds the task text, normalizes results, checks that links resolve, and assigns fact or analysis labels.
  - Persistence: `api/research_store.py` (DuckDB schema `research`).
  - Endpoints: `api/routers/research.py`.
- **Endpoints used:**
  - `POST /v1/web/answers`, always with `mode: "fast"` (10 credits; the default, ultra, costs 100). Docs: https://docs.context.dev/api-reference/web-extraction/answers
  - `POST /v1/web/search` (1 credit per 10 results), used to enrich source titles and snippets. Docs: https://docs.context.dev/api-reference/web-scraping/search
- **Gotchas:**
  - Answers accepts no geo, date or domain fields: put them in `task`, which is limited to 2000 characters.
  - `json_format` is an example object, not a JSON Schema.
  - `sources` is a list of bare URLs and includes the URLs cited in the answer, so being listed does not prove a page was read.
- **Tests:** never hit the live API. Mock with `httpx.MockTransport` (see `tests/test_research.py`) and set `prov._sleep = lambda s: None`.
- **Windows:** run Python scripts with `PYTHONUTF8=1`. Stop the API before reseeding or running `scripts/export_static_data.py`, because of the DuckDB file lock.
