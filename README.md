# CS2 Float-Aware Arbitrage Agent

A self-hosted agent that watches the [CSFloat](https://csfloat.com) market for the
CS2 skins **you actually own** and emails you when something is worth acting on:
a listing under your reserve, or one priced below its float-aware fair value.

Unlike a flat price tracker, fair value here is **float-aware**: it compares each
item only against listings of the same skin, wear tier, and a tight float band, so
a low-float piece isn't measured against worn ones. It's **alert-only**, it never
buys, sells, or lists anything.

New to the signals? See the **[Playbook](PLAYBOOK.md)** for how to read each alert
and what to do with it.

```
CSFloat inventory (your floats)  ─┐
                                  ├─►  float-band comparables  ─►  signals  ─►  email + dashboard
CSFloat market listings  ────────┘         (fair value)          (dedup/cooldown)
```

## Features

- **Zero manual data entry.** Pulls your inventory *with real float values* straight
  from CSFloat's authenticated API, no inspect links, no Steam scraping. Cost basis
  is auto-filled from your CSFloat purchase history for true P&L.
- **Float-band comparable engine.** Median / p25 fair value from same-skin,
  same-wear, similar-float listings, with an adaptive band that widens until it has
  enough comps.
- **Two alert types.** Reserve breach (a listing at/under your price) and undervalued
  (a listing a configurable % under fair value).
- **Flip hunting.** Scans the market for skins you *don't* own that are underpriced
  enough to buy-and-reflip, confirmed against float-band fair value, after fees,
  base-skins only, liquid only. See [Hunt mode](#hunt-mode-flips).
- **Paper trading.** Forward-test the flip strategy with a simulated $1,000 bankroll
  (capital lock + 7-day hold) before risking real money. See [Paper trading](#paper-trading).
- **No inbox flood.** A persisted per-listing cooldown means each deal alerts at most
  once per window; quiet cycles send nothing.
- **Nice emails.** Styled HTML digest with a plain-text fallback.
- **Local dashboard.** Self-contained `dashboard.html` ("tactical terminal" UI)
  shows flip opportunities, portfolio fair value, P&L, and signals. Reads the same
  `state.json` / `hunt_state.json`; falls back to a demo dataset if none is present.
  (Fonts load from Google Fonts at runtime, self-host them for fully offline use.)
- **Runs anywhere.** A Raspberry Pi / VPS via cron, or free via GitHub Actions.
- **Stdlib-only runtime.** No third-party packages to run; `pytest` only for tests.

## Quick start

```bash
git clone <this-repo> && cd cs2-arb
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # Python 3.10+
cp .env.example .env        # fill in your CSFloat key + SMTP creds

python -m scripts.build_holdings          # build watchlist from your inventory
python -m scripts.selftest --send-email   # verify key, inventory, and email
python -m scripts.run_once --live --send-email   # one real cycle
```

View the dashboard (browsers block `file://` fetches, so serve it):

```bash
python -m http.server 8000   # open http://localhost:8000/dashboard.html
```

## Hunt mode (flips)

Find flip candidates on skins you don't own:

```bash
cp hunt_targets.example.json hunt_targets.json   # optional curated watch list
python -m scripts.run_hunt --send-email          # scan + email flip opportunities
```

It pulls cheap listings in your price band ($20-$200 by default), then for each
confirms a **positive ROI after the seller fee** against the float-band median:
skipping Souvenirs, sticker-heavy listings, and illiquid skins (their comps can't be
trusted). Flips appear at the top of the dashboard and in their own email. Tune via
the `HUNT_*` keys in `.env`. Schedule it alongside the portfolio poll (see
[`SCHEDULING.md`](SCHEDULING.md)).

## Paper trading

Test the flip strategy with fake money before risking real capital:

```bash
python -m scripts.run_paper   # buys current flips into a $1,000 paper book
```

Strategy: buy a flip at its listing price (subject to a simulated **$1,000 bankroll
with capital lock**), hold the mandatory **7-day CS2 trade lock**, then sell at the
float-band fair value (minus the seller fee). It tracks equity, realized/unrealized
P&L, win rate, and average ROI, shown in the dashboard's Paper Trading section.

It's **forward** testing (records real listings as they appear), not a historical
backtest, no public source archives per-listing floats, so this is the honest way
to validate the float-aware logic. Caveat: paper fills are optimistic (assumes you
win the buy and resell at fair value), so weight signal accuracy over the raw dollar
figure. Run it on the same schedule as the agent to accumulate results.

## Configuration

Secrets and behaviour live in `.env` (gitignored, see `.env.example`):

| Key | Purpose |
|-----|---------|
| `CSFLOAT_API_KEY` | From csfloat.com → profile → developer tab |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | Email sending (Gmail app password or Outlook) |
| `MAIL_FROM` / `MAIL_TO` | Alert sender / recipient |
| `DIVERGENCE_PCT` | How far under fair value an "undervalued" alert needs (default `0.10`) |
| `COOLDOWN_SECONDS` | Re-alert window per listing (default `21600` = 6h) |

The value floor that decides which items are worth watching is `MIN_MEDIAN_CENTS`
in `scripts/build_holdings.py` (default `$10`). Your per-item `cost_basis` (for P&L)
is preserved across watchlist rebuilds.

## Scheduling

Run every 30 minutes; the persisted cooldown keeps it quiet. See
[`SCHEDULING.md`](SCHEDULING.md) for Raspberry Pi / VPS cron and the included
GitHub Actions workflow (`.github/workflows/cs2-arb.yml`).

## How fair value is computed

For a holding, comparables are listings that match `def_index` + `paint_index` +
category (normal/StatTrak/Souvenir) + wear tier, and fall within `±band` of the
holding's float. The band starts tight and doubles (capped) until it has at least
`min_comps`. Fair value is the median of those comps; p25 is the aggressive "good
deal" line. A `float_rank` (share of comps with a lower float) shows how rare your
float is. Prices are integer cents throughout, matching the CSFloat API.

## Project layout

```
cs2_arb/
  models.py          typed domain models
  wear.py            wear tiers + float ranking
  comparables.py     float-band comparable engine (core logic)
  signals.py         reserve / undervalued signals, persisted dedup + cooldown
  csfloat_client.py  CSFloat API client (listings, inventory, trades, backoff)
  hunt.py            flip finder over skins you don't own (market scan)
  paper.py           paper-trading book ($1k bankroll, capital lock, 7-day hold)
  steam_inventory.py optional Steam inventory fallback
  config.py          .env / env-var settings
  sinks.py           console / HTML email / json-state outputs
  state.py           builds state.json for the dashboard
scripts/             build_holdings · run_once · run_hunt · run_paper · selftest
demo/                fixtures + offline demo
tests/               pytest suite
dashboard.html       read-only dashboard (tactical-terminal UI)
design/              editable design source + handoff notes
```

```bash
pytest -q   # run the suite
```

## Safety

Alert-only by design. The agent reads market data and sends email; it performs no
trades, listings, or purchases. Credentials stay in `.env` and are never committed;
your inventory and listing data are gitignored too.

## Roadmap

- Sticker-craft premium signal (craft value vs. base skin)
- Trade-up contract EV as input prices move
- Weekly portfolio summary email

## Disclaimer

Not affiliated with CSFloat or Valve. Market data can be wrong or stale; verify
before trading. Provided as-is.
