"""Auto-build holdings.json from your CSFloat inventory — fully automated.

Pulls your inventory WITH real float values from CSFloat (/me/inventory), keeps
every skin/knife whose market median is above a value floor, and sets an auto
reserve at RESERVE_FRACTION of that median. No manual float entry, no Steam
inspect links. cost_basis is left null (optional, for P&L).

Run: python -m scripts.build_holdings
"""

from __future__ import annotations

import json
import os
import statistics

from cs2_arb.config import load_settings
from cs2_arb.csfloat_client import CSFloatClient


def _existing_cost_basis() -> dict:
    """Preserve manually-entered cost_basis across rebuilds (keyed by mhn)."""
    if not os.path.exists(HOLDINGS_FILE):
        return {}
    try:
        prev = json.load(open(HOLDINGS_FILE))
    except (ValueError, OSError):
        return {}
    return {r["market_hash_name"]: r.get("cost_basis_cents")
            for r in prev if r.get("cost_basis_cents") is not None}

RESERVE_FRACTION = 0.90    # reserve = 90% of current market median
MIN_MEDIAN_CENTS = 1000    # skip skins under $10 (arbitrage noise)
HOLDINGS_FILE = "holdings.json"


def category_of(item: dict) -> int:
    if item.get("is_stattrak"):
        return 2
    if item.get("is_souvenir"):
        return 3
    return 1


def main() -> None:
    s = load_settings(".env")
    client = CSFloatClient(api_key=s.csfloat_api_key, min_interval=1.0)

    inv = client.get_my_inventory()
    # weapons/knives only (cases, stickers, kits have float_value 0/None)
    weapons = [i for i in inv if (i.get("float_value") or 0) > 0]
    prior_cost = _existing_cost_basis()
    print(f"inventory: {len(inv)} items, {len(weapons)} with a float\n")

    median_cache: dict = {}
    out = []
    for it in weapons:
        mhn = it["market_hash_name"]
        cat = category_of(it)
        key = (mhn, cat)
        if key not in median_cache:
            listings = list(client.iter_listings(
                market_hash_name=mhn, category=cat, sort_by="lowest_price", max_pages=1))
            prices = sorted(l.price_cents for l in listings)
            median_cache[key] = int(statistics.median(prices)) if prices else 0
        median = median_cache[key]
        if median < MIN_MEDIAN_CENTS:
            continue
        reserve = int(round(median * RESERVE_FRACTION))
        out.append({
            "label": mhn,
            "market_hash_name": mhn,
            "def_index": it["def_index"],
            "paint_index": it["paint_index"],
            "paint_seed": it.get("paint_seed"),
            "is_stattrak": bool(it.get("is_stattrak")),
            "is_souvenir": bool(it.get("is_souvenir")),
            "float_value": round(it["float_value"], 6),
            "quantity": 1,
            "cost_basis_cents": prior_cost.get(mhn),  # preserved across rebuilds
            "reserve_cents": reserve,
        })
        print(f"  + {mhn[:52]:52} float {it['float_value']:.4f}  "
              f"median ${median/100:>8,.2f}  reserve ${reserve/100:>8,.2f}")

    with open("holdings.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nwrote holdings.json with {len(out)} fully-populated items. Run:")
    print("  python -m scripts.run_once --live --send-email")


if __name__ == "__main__":
    main()
