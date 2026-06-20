# Handoff: CS2 Arbitrage Dashboard Redesign

## Overview
A redesigned local dashboard for the `cs2-arb` project (FluffyProgramming/cs2-arb). It replaces the
existing `dashboard.html` with a CS2-native "tactical terminal" UI that visualises the same data the
backend already emits: portfolio holdings + fair-value, flip opportunities, and signals. It is a
**read-only view** — no new backend endpoints are required.

## About the Design Files
The files in this bundle are **design references created in HTML**. Two forms are included:

- **`dashboard.html`** — a single, self-contained, zero-dependency file (runtime + styles inlined,
  ~400 KB). This is the actual **drop-in replacement** for the project's current
  `dashboard.html`. It runs as-is when served from the repo root.
- **`CS2 Arb Terminal.dc.html`** — the editable source the bundle was compiled from. Reference only;
  do not edit the compiled `dashboard.html` directly — change the source and recompile if you want to
  keep an editable version.

Because the existing project already serves a static HTML dashboard that `fetch`es JSON, the intended
path here is simply: **drop `dashboard.html` into the repo root, replacing the old one.** No framework
migration is needed. If you instead want to fold it into a different stack (React/Vue/etc.), treat the
HTML as a pixel-accurate spec and rebuild with this README + the token list below.

## Fidelity
**High-fidelity.** Final colors, typography, spacing, and interaction states are all specified here and
present in the files. Recreate pixel-accurately if porting to another stack.

## Data Contract (unchanged from the current project)
The dashboard fetches two files from its own directory and auto-refreshes every 60s. It also re-fetches
on the **RUN CYCLE** button. Shapes match the current `dashboard.html`:

### `state.json` (required)
```jsonc
{
  "generated_at": "2026-06-20T14:03:00Z",          // ISO timestamp
  "totals": {
    "holdings": 7,
    "fair_value": "$2,672.00",                      // pre-formatted strings
    "unrealised": "+$240.50",
    "open_signals": 3
  },
  "signals": [
    { "kind": "undervalued",                        // "undervalued" | "reserve_breach"
      "severity": "high",                           // "high" | "medium"
      "message": "AK-47 | Bloodsport (FT) listed at $24.00 …",
      "url": "https://csfloat.com/item/…" }
  ],
  "portfolio": [
    { "label": "AK-47 | Bloodsport",
      "wear": "Field-Tested",
      "float": "0.2215",
      "quantity": 1,
      "fair_value": "$32.00",                        // pre-formatted
      "p25": "$30.50",
      "n_comps": 6,
      "band_width": 0.004,
      "float_rank_pct": 0.38,                        // 0..1, lower = rarer
      "cost_basis": "$27.00",
      "reserve": "$30.00",
      "unrealised": "+$5.00",                        // pre-formatted
      "unrealised_cents": 500,                       // signed int → drives +/- color
      "cheapest_listing": "$31.20",
      "cheapest_url": "https://csfloat.com/item/…" }
  ]
}
```

### `hunt_state.json` (optional)
```jsonc
{ "flips": [ { "severity": "high", "message": "…", "url": "…" } ] }
```

### Behaviour when data is absent
If `state.json` is missing or returns non-OK (e.g. opened before a cycle is run, or via `file://`),
the dashboard renders a built-in **DEMO dataset** so it always looks complete. When real
`state.json` is found, the status line flips from `SOURCE · DEMO` to `SOURCE · CSFLOAT` and live data
replaces the demo.

> Note on live flips: the real `hunt_state.json` flip objects only carry `{severity, message, url}`,
> so live flip cards render as a message + severity tag + listing link (no margin/buy→fair block).
> The richer flip cards (margin %, buy → fair, float/seed meta) are shown for the DEMO data. If you
> want rich live flip cards, extend `hunt_state.json` flips with structured fields
> (`item, wear, rarity, buy_cents, fair_cents, float, def_index, paint_index, paint_seed`) and map them
> in `mapLive()`.

## Screens / Views
Single full-page dashboard, max content width **1340px**, centered, on a dark radial background.
Top-to-bottom regions:

### 1. Header
- **Left:** 48×48 chamfered scope-reticle logo mark (blue gradient `#2d8fef → #10355c`, white ring +
  crosshair). Wordmark **"CS2 ARBITRAGE TERMINAL"** — "ARBITRAGE" in `#2d8fef`.
- **Status line** below wordmark: pulsing green dot + `LIVE FEED` · `SOURCE · {DEMO|CSFLOAT}` ·
  `SYNC {n}S AGO` (relative clock, updates every second).
- **Right:** chamfered **RUN CYCLE** button (`↻`). Triggers a re-fetch; resets the sync clock.
- A 3px diagonal amber **caution-stripe** divider sits under the header.

### 2. KPI row — 5 tiles, `grid-template-columns: repeat(5, 1fr)`, gap 14px
Each tile: chamfered (bottom-right cut), panel gradient, 2px top accent border, uppercase label,
32px Saira Condensed value, sub-label.
- Portfolio Value · accent `#2d8fef` · sub "7 Holdings"
- Unrealised P&L · accent `#4ee39a` · sub "+9.9% All-Time"
- Open Flips · accent `#e4ae39` · sub "1 High Margin"
- Live Signals · accent `#eb4b4b` · sub "1 Undervalued"
- Best Margin · accent `#d32ce6` · sub "AK · Bloodsport"

### 3. Main split — `grid-template-columns: 1.62fr 1fr`, gap 18px
**Left — Flip Opportunities** (section header: blue tick + count `[n]`). Stacked flip cards:
- Card: panel gradient with a faint rarity-tinted wash on the left, `border-left: 3px {rarityColor}`,
  chamfered bottom-right. Hover: `translateY(-1px)` + lighter border.
- Top: rarity dot + item name (Saira Condensed 17px) + wear chip + severity tag
  (HIGH `#eb4b4b` / MED `#e4ae39` / LOW `#7d8f96`, colored fill + border).
- Middle (rich/demo only): big **net margin %** (30px, green) | divider | **Buy → Fair** prices,
  arrow in rarity color.
- Bottom: mono meta `FLOAT 0.xxxx · DEF n · PAINT n · SEED n` + **VIEW LISTING →** link (`#2d8fef`).

**Right — Signals** (section header: red tick). Cards: `border-left: 3px {severityColor}`, kind chip
(e.g. `UNDERVALUED`, `RESERVE BREACH`) + severity, message text, optional listing link.

### 4. Portfolio table (full width, section header: amber tick)
Panel with chamfered bottom-right; dense table. Columns (right-aligned except Item):
`Item | Fair | p25 | Comps (±band) | Float Rank | Cost | Reserve | Unrealised | Cheapest Live`.
- Item cell: rarity dot + name (Saira Condensed) + sub `wear · float 0.xxxx · xN`.
- Float Rank: 52px track + fill width = rank%, fill color by tier (`<30% #4ee39a`, `<55% #e4ae39`,
  else `#6f8189`) + numeric %.
- Unrealised: green if `unrealised_cents ≥ 0`, red if negative.
- Cheapest Live: blue link.
- Row hover: `background #101c21`.
- Caption under table: "Float rank — % of comparable listings with a lower float. Lower is rarer."

### 5. Footer
Amber `DATA` chip + run/serve instructions, monospace `code` chips
(`python -m scripts.run_once`, `python -m http.server 8000`).

## Interactions & Behavior
- **Auto-refresh:** `setInterval(load, 60000)` equivalent — re-fetches `state.json` + `hunt_state.json`.
- **RUN CYCLE button:** immediate re-fetch + resets the "SYNC … AGO" clock to 0.
- **Sync clock:** ticks every 1s, shows `{n}S AGO` then `{n}M AGO`.
- **Live pulse dot:** `@keyframes` opacity/scale, 1.5s loop.
- **Hover states:** flip cards lift 1px + border lightens; links shift to `#7fc4ff`; table rows tint;
  button gains blue border + glow.
- **Links:** `target="_blank"` to the listing URLs from the data.
- No routing, no forms — read-only dashboard.

## State Management
Minimal client state:
- `now` (ms) — ticks each second for the relative sync label.
- `sourceLabel` — `"DEMO"` until a successful `state.json` fetch, then `"CSFLOAT"`.
- `raw` — the fetched `{ state, flips }`, or `null` → use the built-in demo dataset.
- `generatedAt` — from `state.generated_at`, drives the sync clock.

Two configurable props (exposed as tweaks in the design tool; hard-code equivalents if porting):
- `rarityTiers` (bool, default true) — when false, all rarity colors collapse to the accent color.
- `accentColor` (enum, default `#2d8fef`) — primary accent used for the logo/portfolio KPI.

## Design Tokens

### Colors
| Token | Hex | Use |
|---|---|---|
| Background (deep) | `#070a0b` | page base |
| Background radial | `#13242c → #0a0f12 → #070a0b` | page gradient |
| Panel gradient | `#0f191e → #0b1316` | tiles, cards |
| Table panel | `#0e171b → #0a1215` | portfolio panel |
| Border | `#1b2a31` / `#1c2c33` | panel borders |
| Border (hover) | `#33505b` | card hover |
| Row divider | `#131e23` | table rows |
| Text primary | `#e6eef0` / `#eef5f7` | values, names |
| Text secondary | `#bccace` / `#cdd9dd` | section titles |
| Text muted | `#6f8189` / `#7d8f96` | labels |
| Accent (primary blue) | `#2d8fef` | logo, links, ticks |
| Accent hover blue | `#7fc4ff` | link hover |
| Profit / live green | `#4ee39a` (val), `#9fd6a8` (fair) | gains, fair price |
| Loss / high sev red | `#eb4b4b` | losses, HIGH |
| Amber / med sev | `#e4ae39` | MED, caution stripe, knife rarity |
| Magenta | `#d32ce6` | classified rarity |

### Rarity palette (CS2 standard — the data language)
`consumer #b0c3d9 · industrial #5e98d9 · mil-spec #4b69ff · restricted #8847ff · classified #d32ce6 · covert #eb4b4b · knife/gold #e4ae39 · contraband #cf9b3f`

### Typography
- **Display / headers / numbers:** `Saira Condensed` 600/700, uppercase, letter-spacing 1.2–2.5px.
- **Body / data:** `Saira` 400–600.
- **Mono (meta, code chips):** `JetBrains Mono` 500/600.
- All loaded from Google Fonts (inlined `<link>` in the bundle). KPI value 32px; flip name 17px;
  margin 30px; table body 13–14.5px; labels 10–11px.
- Numeric cells use `font-variant-numeric: tabular-nums`.

### Shape / effects
- Chamfered corners via `clip-path: polygon(...)` — KPI tiles & table cut bottom-right (12–14px);
  flip/signal cards cut bottom-right (8–10px); logo & button cut top-left + bottom-right (9px).
- Borders 1px; rarity/severity accents as 3px `border-left`.
- Glows: `box-shadow: 0 0 8–11px {color}` on dots/ticks; button hover `0 0 22px rgba(45,143,239,.22)`.
- Faint 44px dotted grid overlay over the background (`rgba(255,255,255,.018)`).
- Transitions: `transform .12s`, `border-color .12s`, `color .12s`.

## Assets
- **No image assets.** The logo reticle is pure CSS/SVG; the thumbnail splash is an inline SVG.
- **Fonts:** Saira, Saira Condensed, JetBrains Mono (Google Fonts). For a fully offline/air-gapped
  setup, self-host these and swap the `<link>` — otherwise they load over the network at runtime.

## Files
- `dashboard.html` — self-contained drop-in replacement (use this).
- `CS2 Arb Terminal.dc.html` — editable design source the bundle was compiled from.
- Original project files this replaces / depends on:
  - `dashboard.html` (current, to be replaced)
  - `state.json`, `hunt_state.json` (produced by `python -m scripts.run_once`)
