"""Forward paper-trading harness — test the flip strategy with fake money.

Strategy (chosen): buy a flip candidate at its listing price, hold the mandatory
7-day CS2 trade lock, then sell at the float-band fair value at that time (minus
the seller fee). A simulated bankroll with capital lock means positions tie up
cash for the hold, so results reflect the money you actually have — not infinite
capital.

Honest limits: paper fills are optimistic (assumes you win the buy and resell at
fair value). Watch signal accuracy (do picks revert up?) more than the raw $.

PaperBook is pure: pricing is injected as a `price_of(position)->cents|None`
callable, so it unit-tests with no network.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

HOLD_SECONDS = 7 * 86400


@dataclass
class PaperConfig:
    bankroll_cents: int = 100_000      # $1,000
    hold_seconds: int = HOLD_SECONDS   # 7-day trade lock before selling
    sell_fee: float = 0.02             # CSFloat seller fee
    max_position_cents: Optional[int] = None   # optional per-trade cap


@dataclass
class Position:
    id: str                  # source listing id (dedupe key)
    label: str
    market_hash_name: str
    rarity: int
    float_value: float
    def_index: int
    paint_index: int
    category: int            # 1 normal / 2 stattrak / 3 souvenir
    buy_cents: int
    entry_fair_cents: int
    opened_at: float
    eligible_at: float       # opened_at + hold
    status: str = "open"     # "open" | "sold"
    sold_at: Optional[float] = None
    sell_cents: Optional[int] = None
    net_cents: Optional[int] = None    # realized P&L


PriceFn = Callable[[Position], Optional[int]]


class PaperBook:
    def __init__(self, cfg: PaperConfig, cash_cents: Optional[int] = None,
                 positions: Optional[list[Position]] = None, path: Optional[str] = None):
        self.cfg = cfg
        self.cash_cents = cfg.bankroll_cents if cash_cents is None else cash_cents
        self.positions: list[Position] = positions or []
        self.path = path

    # ---- persistence ------------------------------------------------------
    @classmethod
    def load(cls, path: str, cfg: PaperConfig) -> "PaperBook":
        try:
            d = json.loads(Path(path).read_text())
            pos = [Position(**p) for p in d.get("positions", [])]
            return cls(cfg, cash_cents=d.get("cash_cents", cfg.bankroll_cents),
                       positions=pos, path=path)
        except (FileNotFoundError, ValueError):
            return cls(cfg, path=path)

    def save(self, path: Optional[str] = None) -> None:
        p = path or self.path
        if p:
            Path(p).write_text(json.dumps(
                {"bankroll_cents": self.cfg.bankroll_cents, "cash_cents": self.cash_cents,
                 "positions": [asdict(x) for x in self.positions]}, indent=2))

    # ---- trading ----------------------------------------------------------
    def _held_ids(self) -> set:
        return {p.id for p in self.positions}

    def open_positions(self) -> list[Position]:
        return [p for p in self.positions if p.status == "open"]

    def record_buy(self, *, id, label, market_hash_name, rarity, float_value,
                   def_index, paint_index, category, buy_cents, fair_cents, now: float) -> bool:
        """Open a paper position if not already held and cash allows (capital lock)."""
        if id in self._held_ids():
            return False
        if self.cfg.max_position_cents and buy_cents > self.cfg.max_position_cents:
            return False
        if buy_cents > self.cash_cents:
            return False
        self.cash_cents -= buy_cents
        self.positions.append(Position(
            id=str(id), label=label, market_hash_name=market_hash_name, rarity=rarity,
            float_value=float_value, def_index=def_index, paint_index=paint_index,
            category=category, buy_cents=buy_cents, entry_fair_cents=fair_cents,
            opened_at=now, eligible_at=now + self.cfg.hold_seconds))
        return True

    def settle_due(self, price_of: PriceFn, now: float) -> list[Position]:
        """Sell positions past the 7-day hold at current fair value (minus fee)."""
        sold = []
        for p in self.open_positions():
            if now < p.eligible_at:
                continue
            fair = price_of(p)
            if not fair:          # can't price it right now — leave it open
                continue
            proceeds = round(fair * (1 - self.cfg.sell_fee))
            p.status = "sold"
            p.sold_at = now
            p.sell_cents = fair
            p.net_cents = proceeds - p.buy_cents
            self.cash_cents += proceeds
            sold.append(p)
        return sold

    # ---- reporting --------------------------------------------------------
    def metrics(self, price_of: PriceFn) -> dict:
        closed = [p for p in self.positions if p.status == "sold"]
        opens = self.open_positions()
        realized = sum(p.net_cents or 0 for p in closed)
        wins = sum(1 for p in closed if (p.net_cents or 0) > 0)
        rois = [(p.net_cents or 0) / p.buy_cents for p in closed if p.buy_cents]
        # mark open positions to market
        open_value = 0
        unreal = 0
        for p in opens:
            fair = price_of(p) or p.entry_fair_cents
            open_value += fair
            unreal += round(fair * (1 - self.cfg.sell_fee)) - p.buy_cents
        equity = self.cash_cents + open_value
        return {
            "bankroll_cents": self.cfg.bankroll_cents,
            "cash_cents": self.cash_cents,
            "open_value_cents": open_value,
            "equity_cents": equity,
            "realized_pl_cents": realized,
            "unrealized_pl_cents": unreal,
            "total_return_pct": round((equity - self.cfg.bankroll_cents)
                                      / self.cfg.bankroll_cents * 100, 2),
            "open_count": len(opens),
            "closed_count": len(closed),
            "win_rate": round(wins / len(closed), 3) if closed else None,
            "avg_roi": round(sum(rois) / len(rois), 4) if rois else None,
        }
