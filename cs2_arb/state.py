"""Build the state.json payload the dashboard reads.

One source of truth: portfolio valuation + active signals, computed by the agent
and serialised to disk. The dashboard is a dumb read-only renderer of this file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from .comparables import fair_value
from .models import Holding, Listing, Signal
from .wear import wear_tier


def _money(c: Optional[int]) -> Optional[str]:
    return None if c is None else f"${c / 100:,.2f}"


def build_portfolio(holdings: Sequence[Holding], listings: Sequence[Listing]) -> list[dict]:
    rows = []
    for h in holdings:
        fv = fair_value(h, list(listings))
        unrealised = None
        if fv.median_cents is not None and h.cost_basis_cents is not None:
            unrealised = (fv.median_cents - h.cost_basis_cents) * h.quantity
        rows.append({
            "label": h.label,
            "market_hash_name": h.market_hash_name,
            "wear": wear_tier(h.float_value),
            "float": round(h.float_value, 4),
            "quantity": h.quantity,
            "fair_value": _money(fv.median_cents),
            "fair_value_cents": fv.median_cents,
            "p25": _money(fv.p25_cents),
            "n_comps": fv.n_comps,
            "band_width": round(fv.band_width, 4),
            "float_rank_pct": None if fv.float_rank_pct is None else round(fv.float_rank_pct, 3),
            "cost_basis": _money(h.cost_basis_cents),
            "reserve": _money(h.reserve_cents),
            "unrealised": _money(unrealised),
            "unrealised_cents": unrealised,
            "cheapest_listing": _money(fv.low_listing.price_cents) if fv.low_listing else None,
            "cheapest_url": fv.low_listing.url if fv.low_listing else None,
        })
    return rows


def serialise_signals(signals: Sequence[Signal]) -> list[dict]:
    return [{
        "kind": s.kind,
        "severity": s.severity,
        "holding": s.holding.label,
        "listing_id": s.listing.id,
        "price": _money(s.listing.price_cents),
        "float": round(s.listing.float_value, 4),
        "fair_value": _money(s.fair_value.median_cents),
        "message": s.message,
        "url": s.metadata.get("listing_url", ""),
    } for s in signals]


def build_state(
    holdings: Sequence[Holding],
    listings: Sequence[Listing],
    signals: Sequence[Signal],
) -> dict:
    portfolio = build_portfolio(holdings, listings)
    fair_total = sum(
        (r["fair_value_cents"] or 0) * r["quantity"] for r in portfolio
    )
    unreal_total = sum(r["unrealised_cents"] or 0 for r in portfolio)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totals": {
            "holdings": len(portfolio),
            "fair_value": _money(fair_total),
            "unrealised": _money(unreal_total),
            "open_signals": len(signals),
        },
        "portfolio": portfolio,
        "signals": serialise_signals(signals),
    }


def write_state(path: str, state: dict) -> None:
    Path(path).write_text(json.dumps(state, indent=2))
