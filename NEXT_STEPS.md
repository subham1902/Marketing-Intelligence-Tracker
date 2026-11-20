# Next steps

## A. Go live (you, about 45 minutes; full guide: `docs/GO_LIVE_ORACLE.md`)

1. Create a free Oracle Cloud account and an **Ubuntu 24.04 Ampere A1** VM (2 OCPU / 12 GB). Download its SSH key.
2. In Oracle's Security List, **open ports 80 and 443**.
3. In **GoDaddy DNS**, set the `A @` record to the VM's public IP and keep `www` pointing to `@`. Remove any domain forwarding.
4. SSH into the VM and run this one command:
   `curl -fsSL https://raw.githubusercontent.com/subham1902/Marketing-Intelligence-Tracker/main/deploy/install.sh | sudo bash`
   It asks for your domain and email.
5. Open `https://yourdomain.com` and check that you see the padlock and the Marketing Analysis page.
6. Save the admin token (`grep ADMIN_TOKEN /opt/mit/deploy/.env`) somewhere private.

## B. Optional, same day

- [ ] Add a free **Groq** key as `OPERATOR_LLM_API_KEY` in `/opt/mit/deploy/.env`, then run `docker compose up -d`. AI analysis becomes available to every visitor.
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
