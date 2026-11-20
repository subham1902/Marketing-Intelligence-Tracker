# Deploy checklist (Emergent): about 10 minutes of clicking

Full background: `docs/EMERGENT_HANDOFF.md`. Everything works with **no keys**.

## 1. Import

1. In Emergent, import the GitHub repo `subham1902/Marketing-Intelligence-Tracker` (branch `main`).
2. Backend service:
   - Command: `cd backend && pip install -r requirements.txt && uvicorn server:app --host 0.0.0.0 --port 8001`
   - (`backend/server.py` re-exports `api.main:app`.)
3. Frontend service:
   - Root directory **`web/`** (not `frontend/`).
   - Command: `npm install && npm run build && npm start -- -p 3000`
   - Env: `BACKEND_PORT=8001`, `NEXT_PUBLIC_STATIC_DATA=0`.
4. Backend env (optional): `COMPETE_CORS_ORIGINS=*`, `COMPETE_RESEARCH_PROVIDER=open`. Do **not** set `CONTEXT_DEV_API_KEY`.
5. Deploy. The first boot takes 1–2 minutes. It seeds the demo companies, builds the marts, and loads both `config/research_snapshot.json` and `config/marketing_snapshot.json`.

## 2. Two-minute smoke test (on the live URL)

| # | Do | Expect |
|---|---|---|
| 1 | Open `<url>/api/health` | `status: ok`, `snapshots.marketing_analyses` ≥ 7, `llm_mode` |
| 2 | Open `<url>/dashboard` | Stat cards and "Latest live developments" are filled |
| 3 | Open **Marketing Analysis** → pick **Ather Energy** | A full deck appears instantly with a "Captured <date>" label |
| 4 | Click any evidence chip | A popover shows the quote and an **Open source** link |
| 5 | Click **Five forces** in the rail | The radar plus five rated forces with evidence |
| 6 | Click **Download PDF** | The print dialog opens with an A4 layout |
| 7 | Type "Bajaj Auto" → **Analyse** | Stages run: Gathering → Reading N sources → Analysing → Done. If the server IP is blocked, you get a readable failure with "Open the latest captured analysis" |
| 8 | Ask the guide "how do I see Porter's five forces for Ather?" | The answer has an action button that goes to the section |
| 9 | Phone width (390 px) | No horizontal scroll; section chips scroll sideways |

## 3. Optional: turn on AI analysis (free)

1. Get a free Groq key at https://console.groq.com/keys.
2. In the app, open **Connect LLM** → *API key* → preset **Groq** → paste the key → **Test** → **Save and connect**.
3. Click **Refresh** on any analysis. The badge becomes "AI-assisted · N claims quote-verified".

## 4. Housekeeping

- Rotate the Context.dev key that existed in the local `.env`. It was never committed, but rotate it anyway.
- DuckDB lives in `data/`. On an ephemeral filesystem, analyses run on the host disappear on redeploy, but the snapshots always come back.
