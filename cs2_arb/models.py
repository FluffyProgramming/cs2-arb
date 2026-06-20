"""Typed domain models. Prices are integer cents, matching the CSFloat API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# CSFloat category codes
CATEGORY_ANY = 0
CATEGORY_NORMAL = 1
CATEGORY_STATTRAK = 2
CATEGORY_SOUVENIR = 3


@dataclass(frozen=True)
class Sticker:
    name: str
    slot: int
    scm_price_cents: int = 0  # Steam Community Market price for the sticker


@dataclass(frozen=True)
class Listing:
    """A single CSFloat market listing (subset of fields we use)."""

    id: str
    market_hash_name: str
    def_index: int
    paint_index: int
    paint_seed: int
    float_value: float
    price_cents: int                 # buy_now price (or current bid)
    is_stattrak: bool = False
    is_souvenir: bool = False
    rarity: int = 0                  # CSFloat rarity (1=Consumer … 6=Covert, 7=Contraband)
    type: str = "buy_now"            # "buy_now" | "auction"
    wear_name: str = ""
    stickers: tuple[Sticker, ...] = ()
    url: str = ""
    scm_price_cents: int = 0         # Steam Community Market price (reference)
    scm_volume: int = 0              # Steam sales volume (liquidity hint)

    @property
    def category(self) -> int:
        if self.is_stattrak:
            return CATEGORY_STATTRAK
        if self.is_souvenir:
            return CATEGORY_SOUVENIR
        return CATEGORY_NORMAL

    @property
    def sticker_value_cents(self) -> int:
        return sum(s.scm_price_cents for s in self.stickers)


@dataclass(frozen=True)
class Holding:
    """An item you own, plus the parameters that personalise alerts."""

    label: str                       # human name, e.g. "AK-47 | Bloodsport (TyLoo craft #1)"
    market_hash_name: str
    def_index: int
    paint_index: int
    float_value: float
    is_stattrak: bool = False
    is_souvenir: bool = False
    rarity: int = 0
    paint_seed: Optional[int] = None
    quantity: int = 1
    cost_basis_cents: Optional[int] = None   # what you paid
    # max price you'd pay to acquire another / your "this is cheap" line
    reserve_cents: Optional[int] = None

    @property
    def category(self) -> int:
        if self.is_stattrak:
            return CATEGORY_STATTRAK
        if self.is_souvenir:
            return CATEGORY_SOUVENIR
        return CATEGORY_NORMAL


@dataclass
class FairValue:
    """Result of the comparable engine for one holding."""

    holding: Holding
    n_comps: int
    band_width: float                # final float band half-width used
    median_cents: Optional[int]
    p25_cents: Optional[int]         # aggressive "good deal" line
    low_listing: Optional[Listing]   # cheapest in-band listing
    float_rank_pct: Optional[float]  # 0.0 = you hold the lowest float in the band

    @property
    def has_comps(self) -> bool:
        return self.n_comps > 0


@dataclass
class Signal:
    kind: str                        # "reserve_breach" | "undervalued"
    severity: str                    # "high" | "medium"
    holding: Holding
    listing: Listing
    fair_value: FairValue
    message: str
    metadata: dict = field(default_factory=dict)
