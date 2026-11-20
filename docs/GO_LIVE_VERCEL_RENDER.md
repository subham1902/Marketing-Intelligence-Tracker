# Go live free: Vercel (website) + Render (API) + your GoDaddy domain

- **Website:** Vercel, project root `web/`. Your domain points here.
- **API:** Render free web service, from `render.yaml`. The website proxies `/api/*` to it.
- **Database:** DuckDB, built during each Render build from the demo data and the captured snapshots. The site is never empty. Visitors' new runs last until the API restarts.
- **Staying awake:** `.github/workflows/keepalive.yml` pings the API every 10 minutes, so it doesn't sleep.

## 1. API on Render

1. Sign in at **render.com** with GitHub.
2. Go to **New → Blueprint**, then pick `subham1902/Marketing-Intelligence-Tracker`.
3. Apply. Render creates **mit-api**: free plan, Singapore region.
4. The first build takes about 5 minutes. Then copy the URL, e.g. `https://mit-api.onrender.com`.
5. Check `https://mit-api.onrender.com/api/health`. It should show `"public_mode": true` and `"marketing_analyses": 7`.

## 2. Website on Vercel

1. Sign in at **vercel.com** with GitHub.
2. Go to **Add New → Project**, then import `Marketing-Intelligence-Tracker`.
3. **Root Directory:** `web`. Framework: Next.js (auto-detected).
4. Under **Environment Variables**, add `API_PROXY_TARGET` = `https://mit-api.onrender.com` (your Render URL, with no trailing slash).
5. Deploy, then open the `*.vercel.app` URL and check that Marketing Analysis loads.

## 3. Your GoDaddy domain

1. In Vercel, open your project → **Settings → Domains** → add `yourdomain.com` and `www.yourdomain.com`.
2. In GoDaddy, go to **DNS** for the domain:

| Type | Name | Value |
|---|---|---|
| A | `@` | `76.76.21.21` |
| CNAME | `www` | `cname.vercel-dns.com` |

   Use the exact values Vercel shows, if they differ. Delete any other `A @` record ("Parked") and turn off **Forwarding**.

3. Vercel issues HTTPS automatically once DNS has updated (minutes, sometimes up to an hour).

## 4. Keep the API awake (free)

GitHub repo → **Settings → Secrets and variables → Actions → Variables** → **New variable**:
- Name: `API_HEALTH_URL`
- Value: `https://mit-api.onrender.com/api/health`

## Notes

- **Your admin token** is in Render → mit-api → Environment → `COMPETE_ADMIN_TOKEN`. You only need it to change the AI key or the companies on the live site.
- **AI for every visitor (optional):** set `OPERATOR_LLM_API_KEY` (a free Groq key) in Render → Environment. Render redeploys automatically.
- **Updates:** pushing to `main` redeploys both Render and Vercel automatically.
