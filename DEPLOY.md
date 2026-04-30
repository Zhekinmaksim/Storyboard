# Deploy hermes-story.art

Current production setup: Fly.io runs the API at `api.hermes-story.art`.
The static frontend can be hosted on Vercel or any static host.

```
hermes-story.art          (static host) → web/index.html + app.js + style.css
api.hermes-story.art      (Fly.io)      → scripts/web_server.py
```

The whole thing takes ~15 minutes if you have both accounts and the
domain DNS panel open.

---

## 0. Prereqs

- A registered domain `hermes-story.art`
- Account on [Fly.io](https://fly.io)
- Optional static host account for the frontend
- `flyctl` installed: `brew install flyctl` or `curl -L https://fly.io/install.sh | sh`
- An `OPENROUTER_API_KEY` from openrouter.ai with credits

---

## 1. Deploy the API to Fly.io

From the project root (where `fly.toml` lives):

```bash
# First time only: log in
flyctl auth login

# Pick an app name — must match `app = ` in fly.toml.
# Current production app:
flyctl launch --no-deploy --copy-config --name storyboard-api-billowing-shell-4189

# Set the API key as a secret (never commit it!)
flyctl secrets set OPENROUTER_API_KEY=sk-or-...

# Deploy
flyctl deploy
```

After deploy, you should see:

```
https://storyboard-api-billowing-shell-4189.fly.dev/  → "storyboard · API" page
```

Test the API directly:

```bash
curl https://storyboard-api-billowing-shell-4189.fly.dev/api/health
# {"status":"ok","uptime_seconds":..., ...}
```

### Attach the custom subdomain

```bash
# Tell Fly to provision a TLS cert for api.hermes-story.art
flyctl certs add api.hermes-story.art

# Get the IPs to point your DNS to
flyctl ips list
# v4: 137.66.x.x   (shared)
# v6: 2a09:8280:1::xxxx
```

In your domain's DNS panel, add:

```
A     api    137.66.x.x          (the IPv4 from `flyctl ips list`)
AAAA  api    2a09:8280:1::xxxx   (the IPv6)
```

Wait 1-3 minutes, then:

```bash
flyctl certs check api.hermes-story.art
# Should report "issued" with TLS cert.
curl https://api.hermes-story.art/api/health
```

---

## 2. Deploy the frontend

The frontend is static: `web/index.html`, `web/app.js`, and
`web/style.css`. It can be deployed to Vercel or any static host. No
build step is required.

### Option A — Vercel

The `vercel.json` in the project root tells Vercel to publish the
`web/` folder as static.

```bash
vercel        # first run: create a project, link this folder
vercel --prod # deploys web/ to the production URL
```

Web UI:

1. Go to vercel.com → Add New → Project
2. Import the `Zhekinmaksim/storyboard` repo
3. Framework preset: **Other**
4. Root directory: leave blank (vercel.json handles it)
5. Build command: leave blank
6. Output directory: `web`
7. Deploy

### Option B — Other static host

Upload the `web/` directory as static files. The frontend calls
`https://api.hermes-story.art` by default.

### Attach the apex domain

In the Vercel dashboard → Project → Settings → Domains:

1. Add `hermes-story.art` → Vercel will tell you which DNS records to set
2. In your domain DNS panel, add the A or CNAME records Vercel asks for
   (usually an A record pointing to `76.76.21.21`)
3. Add `www.hermes-story.art` → Vercel will redirect it to the apex

Wait for the green check mark next to both domains.

---

## 3. Verify

Open `https://hermes-story.art` in Firefox. You should see:

- Header with "storyboard — a Hermes Agent skill"
- Hero text "Type a scene. Watch it draw itself."
- Three demo buttons (noir / stairwell / kitchen) — these populate
  from `https://api.hermes-story.art/api/demos`, so if buttons are
  missing the API isn't reachable yet
- The cold-vs-directed image lower on the page

Click "noir" → "Generate storyboard". You should see the board
draw itself live, then the Kimi K2.5 review panel appear, then the
download link.

---

## 4. Optional polish

### Vercel preview deployments for PRs

If using Vercel, preview deployments are on by default. Each PR gets its own URL like
`storyboard-git-fix-xyz.vercel.app`.

### Cache the heavy demo runs

Run the three gallery demos once locally (or via the deployed API)
with `OPENROUTER_API_KEY` set. The Kimi response cache mirrors to
`/data/cache/` inside the Fly container. To make these survive
restarts, attach a Fly volume:

```bash
flyctl volumes create storyboard_cache --size 1 --region ams
# then add to fly.toml:
#   [mounts]
#     source = "storyboard_cache"
#     destination = "/data"
flyctl deploy
```

This way, the demo prompts are free forever.

### Monitor usage

```bash
flyctl logs -a storyboard-api-billowing-shell-4189          # tail logs
flyctl status -a storyboard-api-billowing-shell-4189        # machine status
```

OpenRouter dashboard at openrouter.ai/credits shows API spend.

### Rate limiting

The API has a sliding per-IP hourly limit. Default:
`STORYBOARD_RATE_LIMIT_PER_HOUR=6`. Adjust this Fly env var/secret and
re-deploy if hackathon traffic changes.

---

## 5. Troubleshooting

### "demos:" buttons don't appear

`api.hermes-story.art/api/demos` isn't responding. Check:
1. `flyctl status` shows the machine running
2. DNS has propagated: `dig api.hermes-story.art` returns an IP
3. CORS: check browser console — if you see a CORS error, the
   `STORYBOARD_ALLOWED_ORIGINS` env var on Fly doesn't include your
   domain. Set it: `flyctl secrets set STORYBOARD_ALLOWED_ORIGINS=...`

### SSE drops mid-render

Most likely Cloudflare or another CDN sitting in front of the API is
buffering. The server already sends `X-Accel-Buffering: no`, but if
you've added Cloudflare proxying ON, turn it OFF for `api.hermes-story.art`
(grey cloud, not orange).

### "Server is busy" message

Means 30 jobs running concurrently. Either bump `STORYBOARD_MAX_JOBS`
or scale up to a bigger Fly machine:

```bash
flyctl scale memory 1024 -a storyboard-api-billowing-shell-4189
```

---

## 6. Costs

**Fly.io** — free tier covers 3 shared-cpu-1x machines. With
auto_stop_machines = "stop" and min_machines_running = 0, the API
sleeps when idle and wakes on first request (~3s cold start).
Realistic hackathon traffic: $0.

**Static hosting** — Vercel or another static host is effectively $0
for this frontend.

**OpenRouter / Kimi K2.5** — ~$0.005 per generation. Cache makes the
gallery demos free. Realistic hackathon: $1-10 total.
