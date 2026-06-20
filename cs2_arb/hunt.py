"""Flip finder — market-wide arbitrage on skins you do NOT own.

Pulls cheap candidate listings (CSFloat highest_discount, within a price band,
plus any curated targets), then confirms each against our own float-band fair
value. A candidate is a flip only if, after the seller fee, the expected resale
clears a minimum ROI. Base-skin only: candidates/comps with meaningful sticker
value are excluded, because our fair value doesn't price stickers (yet).

Alert-only. Reuses the comparable engine, Signal, and the alert sinks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from .comparables import fair_value
from .csfloat_client import CSFloatClient
from .models import Holding, Listing, Signal
from .signals import AlertState


@dataclass
class HuntConfig:
    min_price_cents: int = 2000       # $20 floor
    max_price_cents: int = 20000      # $200 ceiling
    min_margin: float = 0.15          # required ROI after fee
    sell_fee: float = 0.02            # CSFloat seller fee (verify current rate)
    min_liquidity_comps: int = 8      # need this many comps to trust + resell
    sticker_max_frac: float = 0.05    # skip if stickers > 5% of price
    max_candidates: int = 40          # cap broad-scan candidates evaluated
    scan_pages: int = 2               # pages of the highest_discount scan
    comp_pages: int = 1               # pages of comps fetched per skin
    cooldown_seconds: float = 6 * 3600


def _low_sticker(l: Listing, frac: float) -> bool:
    return l.price_cents <= 0 or l.sticker_value_cents <= frac * l.price_cents


def _candidate_to_holding(l: Listing) -> Holding:
    return Holding(
        label=l.market_hash_name,
        market_hash_name=l.market_hash_name,
        def_index=l.def_index,
        paint_index=l.paint_index,
        float_value=l.float_value,
        is_stattrak=l.is_stattrak,
        is_souvenir=l.is_souvenir,
        rarity=l.rarity,
    )


def evaluate_candidate(cand: Listing, comps: list[Listing], cfg: HuntConfig) -> Optional[Signal]:
    """Return a FLIP Signal if the candidate clears every gate, else None."""
    if cand.type != "buy_now":
        return None
    # 0) Souvenirs carry a tournament premium our float-band comps can't price,
    #    and they flood the discount feed — exclude them like sticker crafts.
    if cand.is_souvenir:
        return None
    # 1) sticker guard — our fair value ignores stickers, so only judge base skins
    if not _low_sticker(cand, cfg.sticker_max_frac):
        return None
    # 2) base-only comps, excluding the candidate itself
    base_comps = [c for c in comps if c.id != cand.id and _low_sticker(c, cfg.sticker_max_frac)]
    h = _candidate_to_holding(cand)
    fv = fair_value(h, base_comps)
    # 3) liquidity / confidence floor
    if not fv.median_cents or fv.n_comps < cfg.min_liquidity_comps:
        return None
    # 4) margin after fee
    net = fv.median_cents * (1 - cfg.sell_fee) - cand.price_cents
    roi = net / cand.price_cents if cand.price_cents else 0.0
    if roi < cfg.min_margin:
        return None

    sev = "high" if roi >= 2 * cfg.min_margin else "medium"
    msg = (
        f"FLIP — {cand.market_hash_name}: buy ${cand.price_cents / 100:,.2f} "
        f"(float {cand.float_value:.4f}), fair ${fv.median_cents / 100:,.2f} "
        f"(n={fv.n_comps}); est net ${net / 100:,.2f} = {roi:.0%} ROI "
        f"after {cfg.sell_fee:.0%} fee."
    )
    return Signal("flip", sev, h, cand, fv, msg,
                  {"listing_url": cand.url, "net_cents": round(net), "roi": round(roi, 4)})


def find_flips(
    client: CSFloatClient,
    cfg: HuntConfig,
    targets: Optional[list[dict]] = None,
    state: Optional[AlertState] = None,
    now: Optional[float] = None,
) -> list[Signal]:
    now = time.time() if now is None else now

    # --- gather candidates -------------------------------------------------
    candidates: list[Listing] = list(client.iter_listings(
        sort_by="highest_discount", category=0,
        min_price=cfg.min_price_cents, max_price=cfg.max_price_cents,
        max_pages=cfg.scan_pages,
    ))[: cfg.max_candidates]

    for t in (targets or []):
        candidates += list(client.iter_listings(
            market_hash_name=t["market_hash_name"], category=t.get("category", 0),
            sort_by="lowest_price",
            min_price=cfg.min_price_cents, max_price=cfg.max_price_cents,
            max_pages=1,
        ))

    # --- confirm each against float-band fair value ------------------------
    comp_cache: dict = {}
    signals: list[Signal] = []
    seen: set = set()
    for cand in candidates:
        if cand.id in seen:
            continue
        seen.add(cand.id)
        key = (cand.market_hash_name, cand.category)
        if key not in comp_cache:
            comp_cache[key] = list(client.iter_listings(
                market_hash_name=cand.market_hash_name, category=cand.category,
                sort_by="lowest_price", max_pages=cfg.comp_pages,
            ))
        sig = evaluate_candidate(cand, comp_cache[key], cfg)
        if not sig:
            continue
        if state is not None:
            if not state.should_fire(sig.holding, sig.listing, now, cfg.cooldown_seconds):
                continue
            state.mark(sig.holding, sig.listing, now)
        signals.append(sig)

    # best ROI first
    signals.sort(key=lambda s: s.metadata.get("roi", 0), reverse=True)
    return signals
