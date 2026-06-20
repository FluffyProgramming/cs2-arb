# Scheduling the agent (24/7)

Run every 30 min. The persisted cooldown (`alert_state.json`, 6h) means a given
listing emails at most once per window, and empty cycles email nothing — so a
30-min cadence will not flood your inbox.

## Option A — Raspberry Pi / VPS (recommended: you own it, state on disk)

One-time setup on the Pi:

```bash
git clone <your-repo> ~/cs2_arb_demo && cd ~/cs2_arb_demo
python3 -m venv .venv && .venv/bin/pip install -U pip   # needs Python 3.10+
cp .env.example .env        # then fill in your secrets
.venv/bin/python -m scripts.build_holdings   # build the watchlist
chmod +x run.sh
```

Add to `crontab -e` (adjust the path to where you cloned it):

```cron
# poll YOUR holdings every 30 min, email new signals
*/30 * * * * /home/pi/cs2_arb_demo/run.sh >> /home/pi/cs2_arb_demo/cron.log 2>&1
# hunt for flips on skins you don't own, every 30 min (offset by 15)
15,45 * * * * cd /home/pi/cs2_arb_demo && .venv/bin/python -m scripts.run_hunt --send-email >> cron.log 2>&1
# refresh watchlist from your inventory weekly (keeps your cost_basis)
0 4 * * 1 cd /home/pi/cs2_arb_demo && .venv/bin/python -m scripts.build_holdings >> cron.log 2>&1
```

The Pi must be powered on; cron does not wake a sleeping machine. A Pi left
running handles this perfectly. Check `cron.log` to confirm it's firing.

## Option B — GitHub Actions (free, no hardware)

`.github/workflows/cs2-arb.yml` is already included. Steps:

1. Push the repo to GitHub (public = free unlimited minutes; private = use an
   hourly cron in the YAML to stay within the free tier).
2. Repo → Settings → Secrets and variables → Actions → add:
   `CSFLOAT_API_KEY`, `STEAM_ID64`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
   `SMTP_PASSWORD`, `MAIL_FROM`, `MAIL_TO`.
3. The workflow runs every 30 min and restores `alert_state.json` from cache
   between runs. Use the Actions tab → "Run workflow" to test immediately.

Note: GitHub may pause scheduled workflows on repos with no recent commits —
push occasionally or it'll go dormant.

## Tuning (in .env unless noted)

- `COOLDOWN_SECONDS` — re-alert window per listing (default 21600 = 6h).
- `DIVERGENCE_PCT` — how far under fair value an "undervalued" alert needs (0.10).
- `MIN_MEDIAN_CENTS` (in `scripts/build_holdings.py`) — value floor; currently
  $10 to cut low-value noise.
