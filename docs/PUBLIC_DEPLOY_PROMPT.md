# AUTONOMOUS TASK: Make the app safe for public use (Oracle Cloud + custom domain)

Work autonomously, make every routine decision yourself and do not stop to ask. Stop only for the human-only steps at the end (creating accounts, DNS); write those as exact instructions instead.

**Repo:** this `compete` folder.
- Branch: `hackathon/market-intelligence`.
- Push to `origin main` after each green step, with the existing secret scan (counts only). Never push to `upstream`.

**Read first:**
- `SPRINT_REPORT.md`
- `docs/DEPLOY_CHECKLIST.md`
- `docs/EMERGENT_HANDOFF.md`
- `api/llm_settings.py`
- `api/routers/research.py`
- `api/routers/marketing.py`
- `api/routers/assistant.py`
- the web Connect LLM panel
- the Next.js API proxy config

**Target architecture (decided):**
- **Hosting:** one Oracle Cloud Always Free VM running Docker Compose. The files already exist and were partly tested; see `deploy/` and `docs/GO_LIVE_ORACLE.md`.
- **Containers:** `caddy` (HTTPS) → `web` (Next.js) → `api` (FastAPI). The API is private.
- **Database:** DuckDB on the `mit_data` volume. No Supabase, no new database.

**Gates:** after each step, run `uv run pytest`, then `cd web && npx tsc --noEmit && npm run lint && npm run build`. Commit only when green: `deploy: <what>`. If something fails 3 times with different approaches, revert it, note it and continue. Windows/PowerShell; `$env:PYTHONUTF8=1`.

---

## Step 1: Public mode with per-session "bring your own key" (security-critical)

**Problem:** `PUT /settings/llm` saves one API key to disk for the whole server. On a public site that means visitor A's key is used for visitor B, and it stays stored on the server.

Add `COMPETE_PUBLIC_MODE` (default `false` locally, `true` in deploy configs). When true:

### 1. Server-side LLM settings become admin-only

- `PUT /settings/llm` returns 403 unless the header `X-Admin-Token` equals `COMPETE_ADMIN_TOKEN`.
- An operator can still set a server default for everyone (e.g. a Groq key) via environment variables only.
- `GET /settings/llm` never returns key material.

### 2. Per-session LLM configuration (BYOK)

- **Frontend storage:** the Connect LLM panel stores the config in `sessionStorage` only. It is cleared when the tab closes. Config fields: `mode` (`off` | `openai_compatible` | `local_browser`), `base_url`, `model`, `api_key`.
- **Copy:** "Your key stays in this browser tab and is sent only with your own requests over HTTPS. It is never saved on our server."
- **Sending it:** every request that may need an LLM (research run, marketing analysis, guide chat, the LLM test) sends it in an `X-LLM-Config` header (JSON, base64-encoded) through the existing API client wrapper.
- **Backend handling:**
  - Parse the header in one dependency (`api/byok.py`).
  - Pass the config explicitly into the background job, and hold it **only in memory** for that job.
  - Never write it to DuckDB, disk, the cache or logs. Stored runs record only a label such as "AI: groq/llama-3.3-70b (visitor key)".
- **Log redaction:** add a filter that masks anything resembling a key, and the `X-LLM-Config` header.
- **Presets:** Groq, OpenAI, OpenRouter, Google Gemini (OpenAI-compatible endpoint), Mistral, Together, DeepSeek, plus "Custom (HTTPS)".
- **Fallback:** if there is no visitor config and no operator default, keep today's free extractive/rule-based behaviour.

### 3. SSRF protection for user-supplied `base_url`

The server will call URLs that visitors type, so protect it:
- Require `https://`.
- Resolve the DNS name and reject private, loopback, link-local and metadata ranges (`10/8`, `172.16/12`, `192.168/16`, `127/8`, `169.254/16`, `::1`, `fc00::/7`, `100.64/10`), including after redirects (disable redirects).
- Cap response size and timeout.
- Add tests: private IP rejected, `http` rejected, preset accepted.

### 4. Per-visitor workspace without accounts

- Issue an anonymous `session_id` (an httpOnly, Secure, SameSite=Lax cookie with a random UUID, set by the API or the Next middleware).
- Add `session_id` to `research_runs`, the marketing analyses, and the guide/activity endpoints if they persist anything, using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
- **List endpoints return:** the shared captured snapshots (`session_id IS NULL`), plus **this visitor's own runs only**. Other visitors' runs are never listed. A run detail returns 404 for another visitor's run, unless the run is a snapshot or the visitor has the share link.
- **Share links:** add a `share_token` per run/analysis (random) so "Copy share link" still works publicly. Allow read-only access with a valid token.

### 5. Abuse limits

These protect the free sources and the server:
- In-memory per-IP and per-session rate limits:
  - research and marketing runs: about 5 per 10 min per session, and 20 per hour per IP
  - guide: about 30/min
- A global concurrency cap for runs (`COMPETE_MAX_CONCURRENT_RUNS=2`, queued beyond that). The UI shows a friendly "busy, queued" status.
- Return 429 with a readable message and surface it in the UI and the Activity drawer.

### 6. CORS and headers

- In public mode, set `COMPETE_CORS_ORIGINS` from the env var (the real domains), not `*`.
- Add basic security headers in Next: `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'self'`.

**Tests (no network):**
- the BYOK header is parsed and never persisted (assert the DB and log contents)
- admin-only PUT
- the SSRF guard
- session isolation of list/detail
- the share token
- 429 responses

## Step 2: "My local AI" option (per session, browser relay)

A hosted server cannot reach a visitor's `localhost`, so the **browser** talks to the visitor's local model.

### Flow

1. The backend gathers evidence as today. If the job's config is `local_browser`, it stops at a new status `awaiting_local_ai` with stage "Waiting for your local AI". It stores the synthesis prompt packets: the existing per-section prompts and numbered evidence.
2. The frontend sees that status, then calls the visitor's local OpenAI-compatible endpoint directly from the page:
   - Ollama `http://localhost:11434/v1/chat/completions`
   - LM Studio `http://localhost:1234/v1/...`
   - a custom URL
3. It runs each packet with a progress bar, then POSTs the raw outputs to `POST /research/{id}/local-synthesis` (and the marketing equivalent).
4. The backend runs **the same validation as server-side AI**: quote verification, the no-new-numbers check, and downgrade labels. It then completes the run.
   - Timeouts and failures fall back to rule-based/extractive output with a clear note.

### Connect panel ("Local AI on this computer")

- Fields: endpoint URL (default `http://localhost:11434`) and model. A "Detect models" button calls `GET /api/tags` (Ollama) or `/v1/models`.
- A "Test" button.
- Inline setup help, generated with the real site origin:
  - **Windows:** `setx OLLAMA_ORIGINS "https://www.<domain>"`, then restart Ollama.
  - **macOS:** `launchctl setenv OLLAMA_ORIGINS "https://www.<domain>"`.
  - **LM Studio:** enable CORS in its server settings.
- Explain that Chrome/Edge may show a "local network access" permission prompt, and that the visitor should click Allow.
- If the browser blocks the request, show the reason, plus the alternative: expose the model through an HTTPS tunnel (`cloudflared tunnel --url http://localhost:11434`) and use "Custom (HTTPS)" instead.
- Detect a blocked permission via `navigator.permissions.query({name: "local-network-access"})` / `"loopback-network"` inside try/catch, where supported.

**Tests:** the backend endpoints for `awaiting_local_ai` → `local-synthesis` → validated completion, with fixtures. On the frontend, keep the relay logic in pure functions; tsc covers them.

## Step 3: Keep the Oracle deploy files in sync

The files in `deploy/` were written and partly tested on 20 Nov: `api.Dockerfile`, `web.Dockerfile`, `docker-compose.yml`, `Caddyfile`, `.env.example`, `install.sh`, `update.sh`, `backup.sh`. **Do not replace them with another platform's config.**

1. Wire the new settings from Steps 1–2 through `deploy/.env.example` and the compose file: `COMPETE_PUBLIC_MODE`, `COMPETE_ADMIN_TOKEN`, `COMPETE_MAX_CONCURRENT_RUNS`, and the optional operator key `OPERATOR_LLM_BASE_URL`, `OPERATOR_LLM_MODEL`, `OPERATOR_LLM_API_KEY`. Implement the operator key as the server-wide default when a visitor brings no key.
2. **The session cookie must be `Secure`** behind Caddy. The API runs with `--proxy-headers`, so use `X-Forwarded-Proto`.
3. Rate limiting must use the real client IP from `X-Forwarded-For`; Caddy is the only proxy. Do not trust a client-supplied value when the request did not come through Caddy.
4. **If Docker Desktop is available on this machine:** run `cd deploy && docker compose build`, then smoke-test locally with `DOMAIN=localhost`. Caddy serves `https://localhost` with a local certificate.
   - Check health, the snapshots, a BYOK test with a fake key (readable auth error), a 429, and session isolation with two browsers.
   - **If Docker isn't available:** run the same checks with uvicorn + `next start`, using `API_PROXY_TARGET=http://127.0.0.1:8000`.
5. Update `docs/GO_LIVE_ORACLE.md` only if behaviour changed. It is the human guide, so keep it accurate.

## Final

- Run the gates, push, and write `DEPLOY_REPORT.md`:
  - what changed
  - the security model (BYOK, SSRF, isolation, limits)
  - test counts
  - the docker-compose smoke results
  - the exact remaining human steps (from `docs/GO_LIVE_ORACLE.md`)
- Stop all servers.

Begin with Step 1 now. Do not ask for confirmation.
