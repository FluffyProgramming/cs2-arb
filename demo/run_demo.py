"""End-to-end demo on fixtures. Run: python -m demo.run_demo

Shows the full pipeline: parse listings -> fair value per holding ->
signals -> alert text. No API key needed; no trades placed.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cs2_arb.comparables import fair_value          # noqa: E402
from cs2_arb.csfloat_client import parse_listing     # noqa: E402
from cs2_arb.models import Holding                    # noqa: E402
from cs2_arb.signals import AlertState, SignalConfig, evaluate  # noqa: E402
from demo.fixtures import (                           # noqa: E402
    AK_DEF, BLOODSPORT_PAINT, DOPPLER_PAINT, KNIFE_DEF, raw_listings,
)


def money(c):
    return "n/a" if c is None else f"${c / 100:,.2f}"


def main() -> None:
    listings = [parse_listing(r) for r in raw_listings()]

    holdings = [
        Holding(
            label="AK-47 | Bloodsport FT (TyLoo craft proxy)",
            market_hash_name="AK-47 | Bloodsport (Field-Tested)",
            def_index=AK_DEF, paint_index=BLOODSPORT_PAINT,
            float_value=0.2215, quantity=4,
            cost_basis_cents=2900, reserve_cents=2600,
        ),
        Holding(
            label="Karambit | Doppler FT (Chrome Cannon proxy)",
            market_hash_name="Karambit | Doppler (Field-Tested)",
            def_index=KNIFE_DEF, paint_index=DOPPLER_PAINT,
            float_value=0.1805, quantity=1,
            cost_basis_cents=64000, reserve_cents=66000,
        ),
    ]

    print("=" * 72)
    print("PORTFOLIO VALUATION (float-band comparables)")
    print("=" * 72)
    for h in holdings:
        fv = fair_value(h, listings)
        pnl = ""
        if fv.median_cents and h.cost_basis_cents:
            delta = fv.median_cents - h.cost_basis_cents
            pnl = f"  | unrealised {('+' if delta >= 0 else '')}{money(delta)}/unit"
        rank = "n/a" if fv.float_rank_pct is None else f"{fv.float_rank_pct:.0%}"
        print(f"\n{h.label}  x{h.quantity}")
        print(f"  fair value (median) {money(fv.median_cents)}  "
              f"p25 {money(fv.p25_cents)}  comps={fv.n_comps} "
              f"band=+/-{fv.band_width:.3f}")
        print(f"  your float {h.float_value:.4f} ranks below {rank} of comps "
              f"(lower=rarer){pnl}")

    print("\n" + "=" * 72)
    print("SIGNALS (alert-only)")
    print("=" * 72)
    cfg = SignalConfig(divergence_pct=0.10)
    state = AlertState()
    signals = evaluate(holdings, listings, cfg, state)
    if not signals:
        print("No signals this cycle.")
    for s in signals:
        print(f"\n[{s.severity.upper()}] {s.message}")
        print(f"        {s.metadata.get('listing_url', '')}")

    # demonstrate dedupe: a second pass fires nothing new
    again = evaluate(holdings, listings, cfg, state)
    print(f"\n(dedupe check) second pass produced {len(again)} new signals "
          f"(expected 0 — cooldown active)")


if __name__ == "__main__":
    main()
