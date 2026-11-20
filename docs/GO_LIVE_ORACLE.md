# Go live on Oracle Cloud (free) with your GoDaddy domain

**Stack:** one free Oracle VM running three containers:
- **caddy**: HTTPS, with certificates obtained and renewed automatically
- **web**: Next.js
- **api**: FastAPI with DuckDB on a persistent volume

Only ports 80 and 443 are public. The API is reachable only through the website's `/api` path.

**Files:** `deploy/` (Dockerfiles, `docker-compose.yml`, `Caddyfile`, `install.sh`, `update.sh`, `backup.sh`).

**Total time:** about 45 minutes, mostly waiting for builds and DNS.

> **Safe to share:** the deploy runs in **public mode** (`COMPETE_PUBLIC_MODE=true` in `deploy/.env`):
> - **Visitors can:** browse everything, run research and Marketing Analysis, and use the guide. Rate limits apply per IP: 6 runs per 10 minutes and 30 guide messages per minute.
> - **Only you can:** change the server AI key, add, edit or delete companies, or run the pipeline. These need the `X-Admin-Token` from `deploy/.env`. To make those changes, run a copy locally, or set them through `.env` and restart.

---

## 1. Create the free server (Oracle Cloud)

1. Sign up at **cloud.oracle.com** → "Start for free".
   - Choose your **home region carefully; it can't be changed later.** Pick India South (Hyderabad) or India West (Mumbai).
   - A card is asked for identity verification. Always Free resources are not charged.
2. Console → **Compute → Instances → Create instance**:
   - **Name:** `mit`
   - **Image:** Canonical **Ubuntu 24.04**
   - **Shape:** Ampere **VM.Standard.A1.Flex**, **2 OCPU / 12 GB** (the current Always Free limit)
   - **Networking:** keep the defaults (a new VCN and public subnet), with **Assign a public IPv4 address** checked
   - **SSH keys:** "Generate a key pair for me", then **download the private key** (for example save it to `C:\Users\<you>\.ssh\mit.key`)
   - **Boot volume:** 100 GB is fine (200 GB is free in total)
3. If you get **"Out of capacity"**: try another availability domain, try 1 OCPU / 6 GB, or retry later. Capacity frees up often.
4. Copy the instance's **Public IP address**.

## 2. Open ports 80 and 443 in Oracle's network

Instance page → **Subnet** link → **Security Lists** → *Default Security List* → **Add Ingress Rules**.

Add two rules:

| Source CIDR | IP protocol | Destination port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

The VM's own firewall is opened by the install script.

## 3. Point your GoDaddy domain at the server

GoDaddy → **My Products** → your domain → **DNS** → **Manage DNS**:

1. **Edit the `A` record with Name `@`** (it may say "Parked"). Set Value = your server's Public IP, TTL = 1/2 hour. Save.
2. **`www`:** GoDaddy usually already has `CNAME www → @`. **Keep it.** If there is no `www` record, add `A www → <Public IP>`.
3. Remove any **Forwarding** set on the domain (Domain settings → Forwarding).

Check from PowerShell after a few minutes: `nslookup yourdomain.com`. It should show the Public IP.

## 4. Install the app (one command)

From PowerShell on your PC:

```powershell
icacls $env:USERPROFILE\.ssh\mit.key /inheritance:r /grant:r "$($env:USERNAME):(R)"
ssh -i $env:USERPROFILE\.ssh\mit.key ubuntu@<PUBLIC-IP>
```

Then on the server:

```bash
curl -fsSL https://raw.githubusercontent.com/subham1902/Marketing-Intelligence-Tracker/main/deploy/install.sh | sudo bash
```

It asks for your **domain** (without `www`) and **email**, then:
- installs Docker
- opens the firewall
- adds swap
- builds and starts everything
- sets up nightly backups

The first build takes 10–20 minutes. On first boot the API seeds the 7 demo companies, the research runs and the marketing analyses (about 1–5 minutes).

## 5. Check it

- `https://yourdomain.com` loads with a padlock, and `https://www.yourdomain.com` redirects to it.
- `https://yourdomain.com/api/health` shows `"marketing_analyses": 7`.
- On the server:
  - status: `cd /opt/mit/deploy && docker compose ps`
  - logs: `docker compose logs -f --tail=100`

If HTTPS fails, DNS isn't pointing at the server yet. Caddy retries automatically, so check `nslookup` and wait.

## Everyday operations

| Task | Command (on the server) |
|---|---|
| Deploy latest code from GitHub `main` | `sudo /opt/mit/deploy/update.sh` |
| View logs | `cd /opt/mit/deploy && docker compose logs -f api` |
| Restart | `cd /opt/mit/deploy && docker compose restart` |
| Manual backup | `sudo /opt/mit/deploy/backup.sh` (saved in `/var/backups/mit`, last 7 kept; nightly at 03:30) |
| Change settings | `nano /opt/mit/deploy/.env` then `docker compose up -d` |
| Optional AI for all visitors | uncomment and set `OPERATOR_LLM_API_KEY` (e.g. a free Groq key) in `.env`, then `docker compose up -d` |

**Restore a backup:**

```bash
cd /opt/mit/deploy && docker compose stop api
docker run --rm -v mit_mit_data:/data -v /var/backups/mit:/b alpine sh -c "rm -rf /data/* && tar xzf /b/<file>.tgz -C /data"
docker compose start api
```

## Visitor-supplied AI keys

Not yet built (see `NEXT_STEPS.md`). Today the AI is either off (free, rule-based and extractive) or the owner's `OPERATOR_LLM_*` key, which serves everyone.

## Notes

- **Keep the VM in use.** Oracle may reclaim Always Free instances that sit idle for long periods.
- **Tested before handover (20 Nov):**
  - The backend installs from `requirements.txt` on Linux.
  - First boot on an empty data folder seeds everything: the dbt build gave PASS=50 when the DuckDB extensions were available, and the image now pre-installs them.
  - The web `/api` proxy reaches the API, and the pages respond.
  - **Not yet tested:** an actual image build on ARM and the Caddy certificate. Docker Hub and Google Fonts were blocked in the test sandbox. Both run on the server during install.
