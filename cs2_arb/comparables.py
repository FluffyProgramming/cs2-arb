"""Float-band comparable engine — the core IP.

Given a holding and a pool of live listings, find genuinely comparable items
(same skin, same category, same wear tier, similar float) and derive a fair
value from them. An adaptive band widens the float window until enough comps
exist, so thin markets still produce an estimate (flagged by n_comps).
"""

from __future__ import annotations

import statistics
from typing import Iterable, Optional

from .models import FairValue, Holding, Listing
from .wear import float_rank_pct, wear_tier


def _same_skin(holding: Holding, listing: Listing) -> bool:
    return (
        holding.def_index == listing.def_index
        and holding.paint_index == listing.paint_index
        and holding.category == listing.category
    )


def find_comps(
    holding: Holding,
    listings: Iterable[Listing],
    *,
    band_width: float = 0.005,
    max_band_width: float = 0.05,
    min_comps: int = 5,
    buy_now_only: bool = True,
) -> tuple[list[Listing], float]:
    """Return (comps, band_width_used).

    Comps match the holding's skin, category, and wear tier, and fall within
    +/- band_width of the holding's float. The band doubles (capped at
    max_band_width) until at least ``min_comps`` are found or the cap is hit.
    """
    target_tier = wear_tier(holding.float_value)
    pool = [
        l
        for l in listings
        if _same_skin(holding, l)
        and wear_tier(l.float_value) == target_tier
        and (not buy_now_only or l.type == "buy_now")
    ]

    width = band_width
    while True:
        comps = [l for l in pool if abs(l.float_value - holding.float_value) <= width]
        if len(comps) >= min_comps or width >= max_band_width:
            return comps, width
        width = min(width * 2, max_band_width)


def _percentile(sorted_vals: list[int], pct: float) -> int:
    """Linear-interpolated percentile (pct in [0,1]) over sorted integer prices."""
    if not sorted_vals:
        raise ValueError("empty")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = pct * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac)


def fair_value(
    holding: Holding,
    listings: Iterable[Listing],
    **kwargs,
) -> FairValue:
    """Compute fair value for a holding from comparable listings."""
    comps, width = find_comps(holding, listings, **kwargs)

    if not comps:
        return FairValue(
            holding=holding,
            n_comps=0,
            band_width=width,
            median_cents=None,
            p25_cents=None,
            low_listing=None,
            float_rank_pct=None,
        )

    prices = sorted(l.price_cents for l in comps)
    low_listing = min(comps, key=lambda l: l.price_cents)
    return FairValue(
        holding=holding,
        n_comps=len(comps),
        band_width=width,
        median_cents=int(statistics.median(prices)),
        p25_cents=_percentile(prices, 0.25),
        low_listing=low_listing,
        float_rank_pct=float_rank_pct(holding.float_value, [l.float_value for l in comps]),
    )
