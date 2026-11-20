# Go live on Oracle Cloud (free) with your GoDaddy domain

**What you get:** one Always Free Oracle VM, always on, with the data kept on its disk.
- **caddy:** HTTPS on ports 80/443. It gets and renews certificates automatically.
- **mit-web:** the Next.js website, on localhost:3000.
- **mit-api:** the FastAPI backend with DuckDB, on localhost:8000. It is not public; the website reaches it at `/api`.

No Docker: both app parts run as normal `systemd` services. Their files are in `deploy/`.

**Time:** about 45 minutes, mostly waiting for the build and DNS.

> **Safe to share:** the server runs in **public mode**.
> - Visitors can browse, run research and Marketing Analysis, and use the guide. Limits per IP: 6 runs per 10 minutes and 30 guide messages per minute.
> - Only you can change the AI key, the tracked companies or the pipeline. These need the admin token in `/etc/mit/mit.env`.

---

## 1. Create the free server (Oracle Cloud)

1. Sign up at **cloud.oracle.com** → *Start for free*.
   - **Choose your home region carefully; it can't be changed later.** Pick India South (Hyderabad) or India West (Mumbai).
   - A card is needed for verification. Always Free resources are not charged.
2. Go to **Compute → Instances → Create instance**:
   - **Image:** Canonical **Ubuntu 24.04**
   - **Shape:** Ampere **VM.Standard.A1.Flex**, **2 OCPU / 12 GB** (the Always Free limit)
   - **Networking:** keep the defaults, with **Assign a public IPv4 address** ticked
   - **SSH keys:** choose *Generate a key pair for me* and **download the private key**, e.g. to `C:\Users\<you>\.ssh\mit.key`
3. If you see **"Out of capacity"**, try another availability domain or 1 OCPU / 6 GB, or retry later.
4. Copy the instance's **Public IP address**.

## 2. Open ports 80 and 443 in Oracle's network

On the instance page, open the **Subnet** link → **Security Lists** → *Default Security List* → **Add Ingress Rules**:

| Source CIDR | IP protocol | Destination port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

The install script opens the VM's own firewall.

## 3. Point your GoDaddy domain at the server

GoDaddy → **My Products** → your domain → **DNS**:

1. **Edit the `A` record named `@`** (it may say "Parked"). Set the value to the server's Public IP and the TTL to ½ hour.
2. For **`www`**, keep the existing `CNAME www → @`. If there is no `www` record, add `A www → <Public IP>`.
3. Turn off any **Forwarding** on the domain.

After a few minutes, check from PowerShell with `nslookup yourdomain.com`. It should show the Public IP.

## 4. Install the app (one command)

From PowerShell on your PC:

```powershell
icacls $env:USERPROFILE\.ssh\mit.key /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

```powershell
ssh -i $env:USERPROFILE\.ssh\mit.key ubuntu@<PUBLIC-IP>
```

Then on the server:

```bash
curl -fsSL https://raw.githubusercontent.com/subham1902/Marketing-Intelligence-Tracker/main/deploy/install.sh | sudo bash
```

It asks for your **domain** (without `www`) and **email**. Then it:
- installs Python, Node 20 and Caddy
- opens the firewall and adds swap
- builds the app and starts the services
- schedules a nightly backup

The first run takes about 10–15 minutes. On first boot the API loads the 7 companies, the research runs and the marketing analyses, which takes 1–5 minutes.

## 5. Check it

- `https://yourdomain.com` loads with a padlock, and `www` redirects to it.
- `https://yourdomain.com/api/health` shows `"public_mode": true` and `"marketing_analyses": 7`.
- On the server, `systemctl status mit-api mit-web caddy` shows all three as **active (running)**.

**If HTTPS fails:** DNS isn't pointing at the server yet, or port 443 isn't open in step 2. Caddy retries by itself, so check with `nslookup` and wait. Read the details with `journalctl -u caddy -n 50`.

## Everyday operations (on the server)

| Task | Command |
|---|---|
| Deploy the latest code from GitHub `main` | `sudo /opt/mit/deploy/update.sh` |
| Logs | `journalctl -u mit-api -f` (or `mit-web`, `caddy`) |
| Restart | `sudo systemctl restart mit-api mit-web` |
| Change settings | `sudo nano /etc/mit/mit.env`, then `sudo systemctl restart mit-api` |
| Give every visitor AI analysis | set `OPERATOR_LLM_API_KEY` (a free Groq key) in `/etc/mit/mit.env`, then restart `mit-api` |
| Your admin token | `sudo grep ADMIN_TOKEN /etc/mit/mit.env` |
| Manual backup | `sudo /opt/mit/deploy/backup.sh` (saved in `/var/backups/mit`; the last 7 are kept; runs nightly at 03:30) |

**Restore a backup:**

```bash
sudo systemctl stop mit-api
sudo rm -rf /var/lib/mit/* && sudo tar xzf /var/backups/mit/<file>.tgz -C /var/lib/mit && sudo chown -R mit:mit /var/lib/mit
sudo systemctl start mit-api
```

## Notes

- **Keep the VM in use.** Oracle can reclaim Always Free instances that sit idle for a long time. A live website counts as use.
- **Where things live:** code in `/opt/mit`, data in `/var/lib/mit`, settings in `/etc/mit/mit.env` (never in Git).
- **Visitors bringing their own AI key:** not built yet. It's on the list in `NEXT_STEPS.md`.
