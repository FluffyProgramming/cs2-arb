# Playbook: using the agent effectively

This is a **screener and alarm, not an oracle.** It surfaces candidates and does the
float-aware comparison you'd otherwise do by hand, then leaves the decision to you.
It never trades. Nothing happens until you act on an alert.

> Not financial advice. CS2 skins are a volatile, low-liquidity market; comps can be
> wrong or stale. Verify every buy yourself.

## The two signals

**RESERVE BREACH** (high / red): a listing dropped to or below the price *you* set
as worth-it for that item.
- Best when you actually want another copy, or it's a skin you actively flip.
- Also an early warning that the item's floor may be sliding: worth a glance even if
  you don't buy.

**UNDERVALUED** (medium / amber): a listing is priced a configurable % below the
float-band median fair value.
- The real arbitrage flag: buy under comps, resell near fair value, keep the spread.

## The 60-second vet (before every buy)

Open the listing from the alert button, then check:

1. **Float**: confirm it genuinely sits in the comp band, not a wider-tier outlier.
2. **Stickers**: the big gotcha. CSFloat's price *includes* sticker value, so a
   "12% under" can really be a sticker-light piece while stickered crafts inflate the
   comp median. If the cheap listing is plain and the comps are stickered, it isn't
   actually underpriced. (Especially watch sticker-heavy skins like AK Bloodsport.)
3. **Comp count (`n`)**: 5 comps is a thin, noisy estimate; 30 is solid. Trust
   high-`n` signals more.
4. **Liquidity & reason**: how often does this skin sell, and *why* is this one
   cheap? Trade hold, bad pattern, or just a motivated seller?
5. **Spread math**: `profit = fair value - listing - CSFloat seller fee - cashout/
   time friction`. Only act when the spread clears fees with margin. (Confirm
   CSFloat's current seller fee before leaning on thin spreads.)

## Reading the numbers

| Field | Meaning |
|-------|---------|
| **fair value** | median price of the float-band comps |
| **p25** | aggressive "genuinely good buy" line, listings at/below p25 are strongest |
| **float rank** | share of comps with a lower float; lower = your float is rarer |
| **`n` comps** | sample size behind the estimate; low `n` = treat with caution |
| **discount %** | how far under fair value the listing sits |
| **severity** | red = reserve breach, amber = undervalued |

## Using it for your own holdings (the dashboard)

Run it in reverse for exits: when **fair value runs well above your cost basis** and
you want to realize, that's your sell read. Cost basis auto-fills from your CSFloat
purchases, so P&L is real. An item under water isn't a sell unless you're cutting.

## Tuning to keep signals sharp

- One item spamming you → raise its `reserve_cents` in `holdings.json`, or raise the
  value floor (`MIN_MEDIAN_CENTS` in `scripts/build_holdings.py`).
- Want only fatter deals → bump `DIVERGENCE_PCT` (e.g. `0.15`) in `.env`.
- Re-alert frequency → `COOLDOWN_SECONDS` (default 6h; one alert per listing per
  window).

## What it deliberately doesn't catch (yet)

Sticker-craft premium, pattern/tier value (fades, blue gems, etc.), and cross-market
arbitrage (Steam / Buff vs CSFloat). For sticker-heavy or pattern-sensitive skins,
treat a signal as "look closer," not gospel. These are roadmap items.

## Quick decision guide

| You see… | Likely move |
|----------|-------------|
| Undervalued, at/below p25, high `n`, plain skin matching comps | Strongest flip candidate, vet and buy |
| Undervalued but cheap listing is sticker-light vs stickered comps | Usually a false deal, skip |
| Reserve breach on a skin you want more of | Cheap entry, vet float/stickers, then buy |
| Reserve breach you don't want | Note it; the floor may be moving, reassess your reserve |
| Low `n` (≈5) signal | Lower confidence, verify harder before acting |
| Your holding's fair value ≫ cost basis | Candidate to sell/realize if you want out |
