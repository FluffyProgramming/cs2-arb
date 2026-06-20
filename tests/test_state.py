from cs2_arb.csfloat_client import parse_listing
from cs2_arb.models import Holding
from cs2_arb.signals import AlertState, SignalConfig, evaluate
from cs2_arb.state import build_state
from demo.fixtures import (AK_DEF, BLOODSPORT_PAINT, DOPPLER_PAINT,
                           KNIFE_DEF, raw_listings)


def setup():
    listings = [parse_listing(r) for r in raw_listings()]
    holdings = [
        Holding(label="AK", market_hash_name="AK-47 | Bloodsport (Field-Tested)",
                def_index=AK_DEF, paint_index=BLOODSPORT_PAINT, float_value=0.2215,
                quantity=4, cost_basis_cents=2900, reserve_cents=2500),
        Holding(label="Karambit", market_hash_name="Karambit | Doppler (Field-Tested)",
                def_index=KNIFE_DEF, paint_index=DOPPLER_PAINT, float_value=0.1805,
                quantity=1, cost_basis_cents=64000, reserve_cents=66000),
    ]
    return holdings, listings


def test_state_shape_and_totals():
    holdings, listings = setup()
    sigs = evaluate(holdings, listings, SignalConfig(), AlertState(), now=1000)
    state = build_state(holdings, listings, sigs)

    assert set(state) >= {"generated_at", "totals", "portfolio", "signals"}
    assert state["totals"]["holdings"] == 2
    assert len(state["portfolio"]) == 2

    ak = next(p for p in state["portfolio"] if p["label"] == "AK")
    # AK median is $32.25; cost basis $29.00; qty 4 -> unrealised +$13.00
    assert ak["fair_value"] == "$32.25"
    assert ak["unrealised_cents"] == (3225 - 2900) * 4
    assert ak["unrealised"] == "$13.00"
    assert 0.0 <= ak["float_rank_pct"] <= 1.0


def test_state_is_json_serialisable():
    import json
    holdings, listings = setup()
    sigs = evaluate(holdings, listings, SignalConfig(), AlertState(), now=1000)
    json.dumps(build_state(holdings, listings, sigs))  # must not raise
