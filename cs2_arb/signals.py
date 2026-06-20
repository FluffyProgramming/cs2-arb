"""Signal layer: turn fair values into actionable, de-duplicated alerts.

Two v1 triggers (both alert-only):
  * reserve_breach  -> an in-band listing is at/below your reserve price.
  * undervalued     -> an in-band listing is priced below fair value by more
                       than ``divergence_pct`` (a buy opportunity).
Dedupe + cooldown stop the same listing re-firing every poll.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .comparables import fair_value
from .models import FairValue, Holding, Listing, Signal


@dataclass
class SignalConfig:
    divergence_pct: float = 0.10     # listing must be >=10% under fair value
    min_comps_for_divergence: int = 5  # don't trust divergence on thin data
    cooldown_seconds: float = 6 * 3600  # 6h before re-alerting same listing


@dataclass
class AlertState:
    """Tracks fired alerts for dedupe/cooldown. PERSIST THIS BETWEEN RUNS.

    Dedupe is per (holding, listing) regardless of signal kind: a given listing
    alerts at most once per cooldown window, so a reserve breach can't re-fire as
    an "undervalued" alert on the next pass.

    For scheduled runs this MUST be loaded from / saved to disk, or every cycle
    starts with an empty memory and re-emails the same listings (inbox flood).
    """

    _fired: dict[str, float] = field(default_factory=dict)
    path: Optional[str] = None

    def _key(self, holding: Holding, listing: Listing) -> str:
        return f"{holding.label}|{listing.id}"

    def should_fire(self, holding, listing, now, cooldown) -> bool:
        last = self._fired.get(self._key(holding, listing))
        return last is None or (now - last) >= cooldown

    def mark(self, holding, listing, now) -> None:
        self._fired[self._key(holding, listing)] = now

    @classmethod
    def load(cls, path: str) -> "AlertState":
        try:
            with open(path) as f:
                fired = json.load(f)
        except (FileNotFoundError, ValueError):
            fired = {}
        return cls(_fired=fired, path=path)

    def prune(self, now: float, max_age: float) -> None:
        """Drop entries older than max_age so the file doesn't grow unbounded."""
        self._fired = {k: t for k, t in self._fired.items() if now - t < max_age}

    def save(self, path: Optional[str] = None) -> None:
        p = path or self.path
        if p:
            with open(p, "w") as f:
                json.dump(self._fired, f)


def _fmt(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def evaluate_holding(
    holding: Holding,
    listings: list[Listing],
    cfg: SignalConfig,
    state: AlertState,
    now: float | None = None,
) -> list[Signal]:
    now = time.time() if now is None else now
    fv = fair_value(holding, listings)
    signals: list[Signal] = []
    if not fv.has_comps:
        return signals

    # Candidate listings: same comp set, i.e. in-band buy_now listings.
    comps, _ = _comps_for(holding, listings)
    for lst in comps:
        # Pick the single highest-priority signal for this listing.
        # Reserve breach (a concrete "buy below your line") outranks a soft
        # divergence flag.
        sig = None
        if holding.reserve_cents is not None and lst.price_cents <= holding.reserve_cents:
            sig = _reserve_signal(holding, lst, fv)
        elif (
            fv.median_cents is not None
            and fv.n_comps >= cfg.min_comps_for_divergence
            and lst.price_cents <= fv.median_cents * (1 - cfg.divergence_pct)
        ):
            sig = _undervalued_signal(holding, lst, fv, cfg)

        # One alert per (holding, listing) per cooldown, regardless of kind.
        if sig and state.should_fire(holding, lst, now, cfg.cooldown_seconds):
            signals.append(sig)
            state.mark(holding, lst, now)

    return signals


def evaluate(
    holdings: Iterable[Holding],
    listings: list[Listing],
    cfg: SignalConfig,
    state: AlertState,
    now: float | None = None,
) -> list[Signal]:
    out: list[Signal] = []
    for h in holdings:
        out.extend(evaluate_holding(h, listings, cfg, state, now))
    return out


# -- helpers -----------------------------------------------------------------

def _comps_for(holding, listings):
    from .comparables import find_comps
    return find_comps(holding, listings)


def _reserve_signal(holding, lst, fv: FairValue) -> Signal:
    msg = (
        f"RESERVE HIT — {holding.label}: listing {_fmt(lst.price_cents)} "
        f"(float {lst.float_value:.4f}) is at/under your reserve "
        f"{_fmt(holding.reserve_cents)}. Fair value ~{_fmt(fv.median_cents)} "
        f"from {fv.n_comps} comps."
    )
    return Signal("reserve_breach", "high", holding, lst, fv, msg,
                  {"listing_url": lst.url})


def _undervalued_signal(holding, lst, fv: FairValue, cfg: SignalConfig) -> Signal:
    discount = 1 - (lst.price_cents / fv.median_cents)
    msg = (
        f"UNDERVALUED — {holding.label}: listing {_fmt(lst.price_cents)} "
        f"(float {lst.float_value:.4f}) is {discount:.0%} under fair value "
        f"{_fmt(fv.median_cents)} (n={fv.n_comps}, band +/-{fv.band_width:.3f}). "
        f"p25 line {_fmt(fv.p25_cents)}."
    )
    return Signal("undervalued", "medium", holding, lst, fv, msg,
                  {"discount": round(discount, 4), "listing_url": lst.url})
