"""Paper-trade the flip strategy on live data. Run: python -m scripts.run_paper

Buys current flip candidates into a $1,000 paper book (capital lock applies),
holds the 7-day CS2 trade lock, then sells at float-band fair value. Writes
paper_state.json for the dashboard. No real money, no trades.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from cs2_arb.comparables import fair_value
from cs2_arb.config import load_settings
from cs2_arb.csfloat_client import CSFloatClient
from cs2_arb.hunt import HuntConfig, find_flips
from cs2_arb.models import Holding
from cs2_arb.paper import PaperBook, PaperConfig

BOOK_FILE = "paper_trades.json"
STATE_FILE = "paper_state.json"


def main() -> None:
    s = load_settings(".env")
    cfg = PaperConfig(bankroll_cents=100_000, sell_fee=s.hunt_sell_fee)
    hunt_cfg = HuntConfig(
        min_price_cents=s.hunt_min_price_cents, max_price_cents=s.hunt_max_price_cents,
        min_margin=s.hunt_min_margin, sell_fee=s.hunt_sell_fee,
        min_liquidity_comps=s.hunt_min_liquidity, max_candidates=s.hunt_max_candidates)

    client = CSFloatClient(api_key=s.csfloat_api_key, min_interval=1.0)
    book = PaperBook.load(BOOK_FILE, cfg)
    now = time.time()

    # 1) buy current flip candidates (subject to bankroll / capital lock)
    flips = find_flips(client, hunt_cfg)
    bought = 0
    for f in flips:
        ok = book.record_buy(
            id=f.listing.id, label=f.holding.label, market_hash_name=f.listing.market_hash_name,
            rarity=f.listing.rarity, float_value=f.listing.float_value,
            def_index=f.listing.def_index, paint_index=f.listing.paint_index,
            category=f.listing.category, buy_cents=f.listing.price_cents,
            fair_cents=f.fair_value.median_cents or f.listing.price_cents, now=now)
        bought += int(ok)

    # 2) price open positions (fetch comps once per unique item)
    comp_cache: dict = {}

    def price_of(p):
        key = (p.market_hash_name, p.category)
        if key not in comp_cache:
            comp_cache[key] = list(client.iter_listings(
                market_hash_name=p.market_hash_name, category=p.category,
                sort_by="lowest_price", max_pages=1))
        h = Holding(label=p.label, market_hash_name=p.market_hash_name,
                    def_index=p.def_index, paint_index=p.paint_index,
                    float_value=p.float_value, is_stattrak=p.category == 2,
                    is_souvenir=p.category == 3)
        return fair_value(h, comp_cache[key]).median_cents

    # 3) sell anything past the 7-day hold, then snapshot
    sold = book.settle_due(price_of, now)
    m = book.metrics(price_of)
    book.save()

    def money(c):
        return None if c is None else f"${c/100:,.2f}"

    positions = []
    for p in book.open_positions():
        fair = price_of(p) or p.entry_fair_cents
        unreal = round(fair * (1 - cfg.sell_fee)) - p.buy_cents
        days_left = max(0, (p.eligible_at - now) / 86400)
        positions.append({
            "label": p.label, "rarity": p.rarity, "float": round(p.float_value, 4),
            "buy": money(p.buy_cents), "fair": money(fair),
            "unrealised": money(unreal), "unrealised_cents": unreal,
            "days_left": round(days_left, 1)})

    Path(STATE_FILE).write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bankroll": money(m["bankroll_cents"]), "cash": money(m["cash_cents"]),
        "equity": money(m["equity_cents"]), "realized_pl": money(m["realized_pl_cents"]),
        "unrealized_pl": money(m["unrealized_pl_cents"]),
        "total_return_pct": m["total_return_pct"], "open_count": m["open_count"],
        "closed_count": m["closed_count"], "win_rate": m["win_rate"], "avg_roi": m["avg_roi"],
        "positions": positions}, indent=2, ensure_ascii=False))

    print(f"paper: bought {bought}, sold {len(sold)} | equity {money(m['equity_cents'])} "
          f"({m['total_return_pct']:+}%) | cash {money(m['cash_cents'])} | open {m['open_count']}")
    print(f"wrote {STATE_FILE}")


if __name__ == "__main__":
    main()
