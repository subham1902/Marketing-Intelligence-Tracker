# Next steps

## A. Go live (about 30 minutes; full guide: `docs/GO_LIVE_VERCEL_RENDER.md`)

1. **Render:** New → Blueprint → this repo, then copy the API URL.
2. **Vercel:** import the repo with Root Directory `web` and set `API_PROXY_TARGET` = the Render URL.
3. **Vercel → Domains:** add `yourdomain.com` and `www`.
4. **GoDaddy DNS:** `A @ → 76.76.21.21` and `CNAME www → cname.vercel-dns.com`. Turn off forwarding.
5. **GitHub → Actions variable:** `API_HEALTH_URL` = `<render-url>/api/health`. This keeps the API awake.
6. Open `https://yourdomain.com` and check that Marketing Analysis loads.

## B. Optional, same day

- [ ] Add a free **Groq** key as `OPERATOR_LLM_API_KEY` in Render → Environment. AI analysis becomes available to every visitor.
- [ ] Rotate the old **Context.dev** key. It was never committed, but rotate it anyway.
- [ ] Fill in **"Mentor feedback we acted on"** in `docs/PITCH.md`.

## C. Product to-dos (next builds, highest value first)

1. **Visitor's own AI key, per browser tab:** visitors paste a Groq or OpenAI key that stays in their tab and is never stored on the server. It needs an SSRF guard for custom URLs.
2. **Private workspaces without accounts:** each visitor sees only their own runs, plus shareable read-only links.
3. **"Use my local AI" relay:** the browser talks to the visitor's own Ollama, and the server validates the results.
4. **Battle-card export:** a one-page competitor summary as a PDF.
5. **Scheduled re-runs with change alerts:** for example, "Ola's tone dropped this week" by email.
6. **More Indian sources:** BSE/NSE announcements and MCA filings for real financials.
7. **Accounts and team workspaces:** sign-in, saved companies and team sharing.

Items 1–3 have a detailed brief in `docs/PUBLIC_DEPLOY_PROMPT.md`.

## D. Known limits (say these honestly in demos)

- Ratings come from transparent keyword rules, so they are crude when there are few sources. The coverage meter shows when that's the case.
- Tone is a news-text word score, not customer sentiment.
- Free news sources can rate-limit a cloud server's IP. The captured analyses are always available as a fallback.
